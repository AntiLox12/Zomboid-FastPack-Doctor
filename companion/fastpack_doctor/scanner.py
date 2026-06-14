from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .discovery import index_mods, resolve_active_mod
from .models import Finding, ModInfo, ModStats, ScanConfig
from .parsers import (
    map_cell_from_path,
    parse_active_profile,
    parse_script_definitions,
    parse_server_ini,
)


TEXTURE_EXTENSIONS = {".png", ".dds", ".ktx", ".pack"}
SOUND_EXTENSIONS = {".ogg", ".wav", ".mp3", ".bank"}
MODEL_EXTENSIONS = {".fbx", ".x", ".obj", ".dae"}
SCRIPT_EXTENSIONS = {".txt"}
IGNORED_DIRECTORIES = {".git", ".svn", "__macosx"}
ASSET_OVERRIDE_EXTENSIONS = (
    TEXTURE_EXTENSIONS | SOUND_EXTENSIONS | MODEL_EXTENSIONS | {".lua", ".txt"}
)


def _version_tuple(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", value))


def _is_version_directory(path: Path) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)*", path.name))


def _normalized_version(value: tuple[int, ...], width: int = 4) -> tuple[int, ...]:
    return value + (0,) * (max(width, len(value)) - len(value))


def _best_version_directory(package_root: Path, game_version: str) -> Path | None:
    target = _normalized_version(_version_tuple(game_version))
    compatible: list[tuple[tuple[int, ...], Path]] = []
    future: list[tuple[tuple[int, ...], Path]] = []
    try:
        children = list(package_root.iterdir())
    except OSError:
        return None

    for child in children:
        if not child.is_dir() or not _is_version_directory(child):
            continue
        version = _normalized_version(_version_tuple(child.name))
        if not version or version[0] != target[0]:
            continue
        if version <= target:
            compatible.append((version, child))
        else:
            future.append((version, child))

    if compatible:
        return max(compatible, key=lambda item: item[0])[1]
    if future:
        return min(future, key=lambda item: item[0])[1]
    return None


def _package_root(mod: ModInfo) -> tuple[Path, Path | None]:
    if _is_version_directory(mod.root):
        return mod.root.parent, mod.root
    if mod.root.name.lower() == "common" and _is_version_directory(mod.root.parent):
        return mod.root.parent.parent, mod.root.parent
    if mod.root.name.lower() == "common":
        return mod.root.parent, None
    return mod.root, None


def _content_roots(mod: ModInfo, game_version: str) -> tuple[list[Path], Path]:
    package_root, selected_version = _package_root(mod)
    if selected_version is None:
        selected_version = _best_version_directory(package_root, game_version)

    roots: list[Path] = []
    candidates = [package_root / "common", selected_version]
    for candidate in candidates:
        if candidate is not None and candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    if not roots:
        roots.append(package_root)
    return roots, package_root


def _iter_files(roots: list[Path], package_root: Path):
    seen: set[Path] = set()
    stack = list(reversed(roots))
    while stack:
        directory = stack.pop()
        try:
            resolved = directory.resolve()
        except OSError:
            resolved = directory
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            if entry.name.lower() in IGNORED_DIRECTORIES:
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if directory == package_root and (
                        entry.name.lower() == "common"
                        or _is_version_directory(Path(entry.path))
                    ):
                        continue
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
            except OSError:
                continue


def _relative_asset(file_path: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            relative = file_path.relative_to(root).as_posix().lower()
            if relative.startswith("common/media/"):
                return relative[len("common/") :]
            return relative
        except ValueError:
            continue
    return file_path.name.lower()


def _classify_role(stats: ModStats) -> str:
    mod_text = f"{stats.mod.mod_id} {stats.mod.name}".lower()
    if stats.map_cells:
        return "map"
    if any(word in mod_text for word in ("patch", "compat", "fix")):
        return "patch"
    content_files = max(stats.file_count, 1)
    if stats.translation_files > 0 and stats.translation_files >= content_files - 3:
        return "localization"
    if stats.texture_files / content_files >= 0.75 and stats.lua_files <= 3:
        return "texture_pack"
    if stats.sound_files / content_files >= 0.65 and stats.lua_files <= 3:
        return "sound_pack"
    if any(word in mod_text for word in ("framework", "library", "lib", "core")):
        return "framework"
    if stats.lua_files > 0 and stats.script_files == 0 and stats.texture_files <= 5:
        return "lua"
    return "content"


def _scan_mod(mod: ModInfo, active_index: int, game_version: str) -> ModStats:
    stats = ModStats(mod=mod, active_index=active_index)
    roots, package_root = _content_roots(mod, game_version)
    definition_counts: Counter[str] = Counter()

    try:
        for file_path in _iter_files(roots, package_root):
            relative = _relative_asset(file_path, roots)
            suffix = file_path.suffix.lower()
            try:
                size = file_path.stat().st_size
            except OSError:
                size = 0

            stats.file_count += 1
            stats.total_bytes += size

            if suffix == ".lua":
                stats.lua_files += 1
                stats.lua_bytes += size
            if suffix in TEXTURE_EXTENSIONS:
                stats.texture_files += 1
                stats.texture_bytes += size
            if suffix in SOUND_EXTENSIONS:
                stats.sound_files += 1
                stats.sound_bytes += size
            if suffix in MODEL_EXTENSIONS:
                stats.model_files += 1
                stats.model_bytes += size
            if "/translate/" in f"/{relative}" or "/translations/" in f"/{relative}":
                stats.translation_files += 1

            if "/media/scripts/" in f"/{relative}" and suffix in SCRIPT_EXTENSIONS:
                stats.script_files += 1
                try:
                    records = parse_script_definitions(file_path, relative)
                except OSError:
                    records = []
                stats.definition_records.extend(records)
                definition_counts.update(record.kind for record in records)

            if "/media/maps/" in f"/{relative}":
                cell = map_cell_from_path(file_path)
                if cell and cell not in stats.map_cells:
                    stats.map_cells.append(cell)

            if suffix in ASSET_OVERRIDE_EXTENSIONS and relative.startswith("media/"):
                stats.relative_assets.append(relative)
    except Exception as exc:  # Keep one broken mod from aborting a pack report.
        stats.scan_error = f"{type(exc).__name__}: {exc}"

    stats.map_cells.sort()
    stats.definitions = dict(sorted(definition_counts.items()))
    stats.role = _classify_role(stats)
    if stats.file_count > 10_000:
        stats.warnings.append("Very high file count; file-system overhead may be significant.")
    if stats.lua_files > 500:
        stats.warnings.append("Very high Lua file count.")
    if stats.mod.version_max and _version_tuple(stats.mod.version_max) < (42,):
        stats.warnings.append(
            f"versionMax={stats.mod.version_max} excludes Build 42."
        )
    if any(part.startswith("41.") for part in mod.info_path.parts):
        stats.warnings.append("Resolved metadata comes from a Build 41 directory.")
    return stats


def _dependency_findings(
    active_tokens: list[str],
    resolved: list[ModInfo | None],
) -> list[Finding]:
    findings: list[Finding] = []
    positions = {
        mod.mod_id: index
        for index, mod in enumerate(resolved)
        if mod is not None
    }

    def resolve_reference(reference: str) -> str:
        if reference in positions:
            return reference
        if "/" in reference:
            suffix = reference.split("/", 1)[1]
            if suffix in positions:
                return suffix
        return reference

    for index, mod in enumerate(resolved):
        if mod is None:
            findings.append(
                Finding(
                    severity="error",
                    code="MISSING_MOD",
                    message=f"Active mod could not be resolved: {active_tokens[index]}",
                    mods=[active_tokens[index]],
                )
            )
            continue

        for required in mod.requires:
            required_id = resolve_reference(required)
            if required_id not in positions:
                findings.append(
                    Finding(
                        severity="error",
                        code="MISSING_REQUIREMENT",
                        message=f"{mod.mod_id} requires missing mod {required_id}.",
                        mods=[mod.mod_id, required_id],
                    )
                )
            elif positions[required_id] > index:
                findings.append(
                    Finding(
                        severity="warning",
                        code="REQUIREMENT_AFTER_DEPENDENT",
                        message=(
                            f"{required_id} is loaded after dependent mod {mod.mod_id}."
                        ),
                        mods=[required_id, mod.mod_id],
                    )
                )

        for target in mod.load_after:
            target_id = resolve_reference(target)
            if target_id in positions and positions[target_id] > index:
                findings.append(
                    Finding(
                        severity="warning",
                        code="LOAD_AFTER_VIOLATION",
                        message=f"{mod.mod_id} declares it should load after {target_id}.",
                        mods=[mod.mod_id, target_id],
                    )
                )

        for target in mod.load_before:
            target_id = resolve_reference(target)
            if target_id in positions and positions[target_id] < index:
                findings.append(
                    Finding(
                        severity="warning",
                        code="LOAD_BEFORE_VIOLATION",
                        message=f"{mod.mod_id} declares it should load before {target_id}.",
                        mods=[mod.mod_id, target_id],
                    )
                )
        for target in mod.incompatible:
            target_id = resolve_reference(target)
            if target_id in positions:
                findings.append(
                    Finding(
                        severity="error",
                        code="INCOMPATIBLE_MODS_ACTIVE",
                        message=f"{mod.mod_id} declares {target} incompatible.",
                        mods=[mod.mod_id, target_id],
                    )
                )
    return findings


def _provider_findings(
    active_tokens: list[str],
    mod_index: dict[str, list[ModInfo]],
) -> list[Finding]:
    findings: list[Finding] = []
    checked: set[str] = set()
    for token in active_tokens:
        candidate_ids = [token]
        if token not in mod_index and "/" in token:
            candidate_ids.append(token.split("/", 1)[1])
        mod_id = next((value for value in candidate_ids if value in mod_index), None)
        if not mod_id or mod_id in checked:
            continue
        checked.add(mod_id)
        providers = {
            info.workshop_id or "local"
            for info in mod_index[mod_id]
        }
        if len(providers) > 1:
            findings.append(
                Finding(
                    severity="warning",
                    code="AMBIGUOUS_MOD_PROVIDER",
                    message=(
                        f"{mod_id} is supplied by multiple providers; resolution may "
                        "change after updates."
                    ),
                    mods=[mod_id],
                    details={"providers": sorted(providers)},
                )
            )
    return findings


def _server_findings(
    server_ini: Path | None,
    active_tokens: list[str],
    resolved: list[ModInfo | None],
) -> tuple[list[Finding], dict[str, Any]]:
    if not server_ini:
        return [], {"path": None, "available": False}
    workshop_items, server_mods = parse_server_ini(server_ini)
    if not server_ini.is_file():
        return [], {"path": str(server_ini), "available": False}

    findings: list[Finding] = []
    expected_mods = [
        mod.mod_id if mod is not None else active_tokens[index]
        for index, mod in enumerate(resolved)
    ]
    expected_workshop = []
    for mod in resolved:
        if mod and mod.workshop_id and mod.workshop_id not in expected_workshop:
            expected_workshop.append(mod.workshop_id)

    if server_mods != expected_mods:
        findings.append(
            Finding(
                severity="warning",
                code="SERVER_MODS_MISMATCH",
                message=(
                    "The server Mods= list differs from the scanned active profile."
                ),
                details={
                    "missing_from_server": [
                        value for value in expected_mods if value not in server_mods
                    ],
                    "extra_on_server": [
                        value for value in server_mods if value not in expected_mods
                    ],
                },
            )
        )
    if workshop_items != expected_workshop:
        findings.append(
            Finding(
                severity="warning",
                code="SERVER_WORKSHOP_ORDER_MISMATCH",
                message=(
                    "WorkshopItems= does not match the resolved Workshop provider order."
                ),
                details={
                    "expected": expected_workshop,
                    "actual": workshop_items,
                },
            )
        )
    return findings, {
        "path": str(server_ini),
        "available": True,
        "workshop_items": workshop_items,
        "mods": server_mods,
        "comparison_incomplete": any(mod is None for mod in resolved),
    }


def _conflict_findings(stats: list[ModStats]) -> list[Finding]:
    findings: list[Finding] = []
    definitions: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    map_cells: dict[str, list[str]] = defaultdict(list)
    assets: dict[str, list[str]] = defaultdict(list)

    for mod_stats in stats:
        for record in mod_stats.definition_records:
            definitions[(record.kind, record.identifier.lower())].append(
                (mod_stats.mod.mod_id, record.file)
            )
        for cell in mod_stats.map_cells:
            map_cells[cell].append(mod_stats.mod.mod_id)
        for asset in mod_stats.relative_assets:
            assets[asset].append(mod_stats.mod.mod_id)

    for (kind, identifier), owners in definitions.items():
        unique_mods = list(dict.fromkeys(owner[0] for owner in owners))
        if len(unique_mods) < 2:
            continue
        findings.append(
            Finding(
                severity="warning",
                code="DUPLICATE_DEFINITION",
                message=(
                    f"Multiple mods define {kind} ID {identifier}; "
                    f"{unique_mods[-1]} wins by current load order."
                ),
                mods=unique_mods,
                details={
                    "winner": unique_mods[-1],
                    "locations": owners[:20],
                },
            )
        )

    for cell, owners in map_cells.items():
        unique_mods = list(dict.fromkeys(owners))
        if len(unique_mods) > 1:
            findings.append(
                Finding(
                    severity="error",
                    code="MAP_CELL_OVERLAP",
                    message=f"Map cell {cell} is supplied by multiple mods.",
                    mods=unique_mods,
                )
            )

    asset_conflicts: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for asset, owners in assets.items():
        unique_mods = list(dict.fromkeys(owners))
        if len(unique_mods) > 1:
            asset_conflicts[tuple(unique_mods)].append(asset)
    grouped_assets = sorted(
        asset_conflicts.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )
    for owners, paths in grouped_assets[:100]:
        findings.append(
            Finding(
                severity="info",
                code="ASSET_OVERRIDE",
                message=(
                    f"{owners[-1]} overrides {len(paths)} shared asset path(s) "
                    f"from earlier mods."
                ),
                mods=list(owners),
                details={
                    "winner": owners[-1],
                    "count": len(paths),
                    "examples": sorted(paths)[:20],
                },
            )
        )
    if len(grouped_assets) > 100:
        findings.append(
            Finding(
                severity="info",
                code="ASSET_OVERRIDE_TRUNCATED",
                message=(
                    f"{len(grouped_assets) - 100} additional mod combinations with "
                    "asset overrides were omitted from the report."
                ),
            )
        )
    return findings


def _duplicate_profile_findings(active_tokens: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    positions: dict[str, list[int]] = defaultdict(list)
    for index, token in enumerate(active_tokens):
        positions[token].append(index + 1)
    for token, indexes in positions.items():
        if len(indexes) > 1:
            findings.append(
                Finding(
                    severity="warning",
                    code="DUPLICATE_ACTIVE_ENTRY",
                    message=f"{token} appears more than once in the active profile.",
                    mods=[token],
                    details={"positions": indexes},
                )
            )
    return findings


def _console_summary(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {"path": str(path) if path else None, "available": False}
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as exc:
        return {"path": str(path), "available": False, "error": str(exc)}

    error_lines = [
        line.strip()
        for line in lines
        if re.search(r"\b(ERROR|Exception|Stack trace|attempt to)\b", line, re.IGNORECASE)
    ]
    return {
        "path": str(path),
        "available": True,
        "line_count": len(lines),
        "error_line_count": len(error_lines),
        "recent_errors": error_lines[-100:],
    }


def _runtime_summary(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {"path": str(path) if path else None, "available": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": str(path), "available": False, "error": str(exc)}
    data["path"] = str(path)
    data["available"] = True
    return data


def _baseline_changes(
    baseline_path: Path | None,
    current_stats: list[ModStats],
) -> list[dict[str, Any]]:
    if not baseline_path or not baseline_path.is_file():
        return []
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    previous = {
        row["mod"]["mod_id"]: row
        for row in baseline.get("mods", [])
        if row.get("mod", {}).get("mod_id")
    }
    changes: list[dict[str, Any]] = []
    for stats in current_stats:
        old = previous.get(stats.mod.mod_id)
        if not old:
            changes.append({"mod_id": stats.mod.mod_id, "status": "added"})
            continue
        file_delta = stats.file_count - int(old.get("file_count", 0))
        byte_delta = stats.total_bytes - int(old.get("total_bytes", 0))
        version_before = old.get("mod", {}).get("mod_version")
        if file_delta or byte_delta or version_before != stats.mod.mod_version:
            changes.append(
                {
                    "mod_id": stats.mod.mod_id,
                    "status": "changed",
                    "version_before": version_before,
                    "version_after": stats.mod.mod_version,
                    "file_delta": file_delta,
                    "byte_delta": byte_delta,
                }
            )
    current_ids = {stats.mod.mod_id for stats in current_stats}
    for mod_id in previous.keys() - current_ids:
        changes.append({"mod_id": mod_id, "status": "removed"})
    return changes


def _profile_hash(active_tokens: list[str], stats: list[ModStats]) -> str:
    digest = hashlib.sha256()
    for token in active_tokens:
        digest.update(token.encode("utf-8", errors="replace"))
        digest.update(b"\0")
    for row in stats:
        digest.update(row.mod.mod_id.encode("utf-8", errors="replace"))
        digest.update((row.mod.mod_version or "").encode("utf-8", errors="replace"))
        digest.update(str(row.file_count).encode("ascii"))
        digest.update(str(row.total_bytes).encode("ascii"))
    return digest.hexdigest()


def scan(config: ScanConfig) -> dict[str, Any]:
    active_tokens, active_maps = parse_active_profile(config.active_file)
    mod_index = index_mods(config.local_mods, config.workshop_roots)
    resolved = [
        resolve_active_mod(token, mod_index, config.game_version)
        for token in active_tokens
    ]

    stats = [
        _scan_mod(mod, index, config.game_version)
        for index, mod in enumerate(resolved)
        if mod is not None
    ]
    findings = _duplicate_profile_findings(active_tokens)
    findings.extend(_provider_findings(active_tokens, mod_index))
    findings.extend(_dependency_findings(active_tokens, resolved))
    findings.extend(_conflict_findings(stats))
    server_findings, server_config = _server_findings(
        config.server_ini,
        active_tokens,
        resolved,
    )
    findings.extend(server_findings)
    for row in stats:
        if row.scan_error:
            findings.append(
                Finding(
                    severity="warning",
                    code="MOD_SCAN_ERROR",
                    message=f"Could not fully scan {row.mod.mod_id}: {row.scan_error}",
                    mods=[row.mod.mod_id],
                )
            )
        for warning in row.warnings:
            findings.append(
                Finding(
                    severity="warning",
                    code="MOD_STRUCTURE_WARNING",
                    message=f"{row.mod.mod_id}: {warning}",
                    mods=[row.mod.mod_id],
                )
            )

    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(
        key=lambda finding: (
            severity_order.get(finding.severity, 9),
            finding.code,
            finding.message,
        )
    )

    totals = {
        "active_entries": len(active_tokens),
        "resolved_mods": len(stats),
        "files": sum(row.file_count for row in stats),
        "bytes": sum(row.total_bytes for row in stats),
        "lua_files": sum(row.lua_files for row in stats),
        "script_files": sum(row.script_files for row in stats),
        "texture_files": sum(row.texture_files for row in stats),
        "sound_files": sum(row.sound_files for row in stats),
        "model_files": sum(row.model_files for row in stats),
        "definitions": dict(
            Counter(
                {
                    kind: sum(row.definitions.get(kind, 0) for row in stats)
                    for kind in {
                        kind
                        for row in stats
                        for kind in row.definitions
                    }
                }
            )
        ),
        "findings": dict(Counter(finding.severity for finding in findings)),
    }

    return {
        "schema_version": 1,
        "tool_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game_version": config.game_version,
        "profile_hash": _profile_hash(active_tokens, stats),
        "inputs": {
            "active_file": str(config.active_file),
            "local_mods": str(config.local_mods),
            "workshop_roots": [str(path) for path in config.workshop_roots],
            "console_file": str(config.console_file) if config.console_file else None,
            "runtime_file": str(config.runtime_file) if config.runtime_file else None,
            "server_ini": str(config.server_ini) if config.server_ini else None,
        },
        "totals": totals,
        "active_order": active_tokens,
        "active_maps": active_maps,
        "mods": [row.to_dict() for row in stats],
        "top_by_size": [
            row.mod.mod_id
            for row in sorted(stats, key=lambda item: item.total_bytes, reverse=True)[
                : config.top
            ]
        ],
        "top_by_files": [
            row.mod.mod_id
            for row in sorted(stats, key=lambda item: item.file_count, reverse=True)[
                : config.top
            ]
        ],
        "findings": [finding.to_dict() for finding in findings],
        "console": _console_summary(config.console_file),
        "runtime": _runtime_summary(config.runtime_file),
        "server_config": server_config,
        "changes": _baseline_changes(config.baseline_file, stats),
    }
