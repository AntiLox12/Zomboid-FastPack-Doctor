from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path

from .models import ModInfo
from .parsers import parse_mod_info


def _registry_steam_path() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
            path = Path(value)
            return path if path.is_dir() else None
    except (OSError, ImportError):
        return None


def discover_steam_root(explicit: Path | None = None) -> Path | None:
    candidates = [
        explicit,
        Path(os.environ["FASTPACK_STEAM"]) if os.environ.get("FASTPACK_STEAM") else None,
        _registry_steam_path(),
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "steamapps").is_dir():
            return candidate.resolve()
    return None


def discover_steam_libraries(steam_root: Path) -> list[Path]:
    libraries = [steam_root.resolve()]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf.is_file():
        return libraries

    text = vdf.read_text(encoding="utf-8-sig", errors="replace")
    for raw_path in re.findall(r'"path"\s+"([^"]+)"', text):
        path = Path(raw_path.replace("\\\\", "\\"))
        if path.is_dir() and path.resolve() not in libraries:
            libraries.append(path.resolve())
    return libraries


def discover_workshop_roots(steam_root: Path | None) -> list[Path]:
    if not steam_root:
        return []
    roots: list[Path] = []
    for library in discover_steam_libraries(steam_root):
        candidate = library / "steamapps" / "workshop" / "content" / "108600"
        if candidate.is_dir():
            roots.append(candidate.resolve())
    return roots


def default_zomboid_home() -> Path:
    return Path.home() / "Zomboid"


def default_local_mods() -> Path:
    return default_zomboid_home() / "mods"


def default_active_file() -> Path:
    return default_local_mods() / "default.txt"


def default_console_file() -> Path:
    return default_zomboid_home() / "console.txt"


def default_runtime_file() -> Path:
    return default_zomboid_home() / "Lua" / "FastPackDoctor" / "runtime.json"


def _workshop_id_for(info_path: Path, workshop_roots: list[Path]) -> str | None:
    for root in workshop_roots:
        try:
            relative = info_path.relative_to(root)
        except ValueError:
            continue
        return relative.parts[0] if relative.parts else None
    return None


def _is_candidate_info(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return not bool(lowered & {"__macosx", ".git", ".svn"})


def index_mods(
    local_mods: Path,
    workshop_roots: list[Path],
) -> dict[str, list[ModInfo]]:
    index: dict[str, list[ModInfo]] = defaultdict(list)
    search_roots = [local_mods] + workshop_roots

    for root in search_roots:
        if not root.is_dir():
            continue
        for info_path in root.rglob("mod.info"):
            if not _is_candidate_info(info_path):
                continue
            workshop_id = _workshop_id_for(info_path, workshop_roots)
            try:
                info = parse_mod_info(info_path, workshop_id)
            except OSError:
                continue
            if info:
                index[info.mod_id].append(info)
    return dict(index)


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


def _layout_version(info: ModInfo) -> tuple[int, ...]:
    parent = info.info_path.parent
    if re.fullmatch(r"\d+(?:\.\d+)*", parent.name):
        return _version_tuple(parent.name)
    if (
        parent.name.lower() == "common"
        and re.fullmatch(r"\d+(?:\.\d+)*", parent.parent.name)
    ):
        return _version_tuple(parent.parent.name)
    return ()


def _version_score(version: tuple[int, ...], target: tuple[int, ...]) -> tuple[int, tuple[int, ...]]:
    if not version:
        return 0, ()
    width = max(4, len(version), len(target))
    normalized_version = version + (0,) * (width - len(version))
    normalized_target = target + (0,) * (width - len(target))
    if normalized_version[0] != normalized_target[0]:
        return -2, normalized_version
    if normalized_version <= normalized_target:
        return 2, normalized_version
    return 1, tuple(-part for part in normalized_version)


def _candidate_score(
    info: ModInfo,
    requested_workshop_id: str | None,
    game_version: str,
) -> tuple[int, int, int, tuple[int, ...], int]:
    target = _version_tuple(game_version)
    requested_match = int(
        requested_workshop_id is not None and info.workshop_id == requested_workshop_id
    )
    compatibility, version = _version_score(_layout_version(info), target)
    local = int(info.workshop_id is None)
    parent_name = info.info_path.parent.name.lower()
    parent_parent_name = info.info_path.parent.parent.name.lower()
    if re.fullmatch(r"\d+(?:\.\d+)*", parent_name):
        layout_priority = 3
    elif parent_name == "common" and re.fullmatch(
        r"\d+(?:\.\d+)*", parent_parent_name
    ):
        layout_priority = 2
    elif parent_name == "common":
        layout_priority = 1
    else:
        layout_priority = 0
    return requested_match, local, compatibility, version, layout_priority


def resolve_active_mod(
    token: str,
    index: dict[str, list[ModInfo]],
    game_version: str = "42.19",
) -> ModInfo | None:
    requested_workshop_id: str | None = None
    mod_id = token
    candidates = index.get(token, [])
    if not candidates and "/" in token:
        requested_workshop_id, mod_id = token.split("/", 1)
        candidates = index.get(mod_id, [])
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda info: _candidate_score(info, requested_workshop_id, game_version),
    )
