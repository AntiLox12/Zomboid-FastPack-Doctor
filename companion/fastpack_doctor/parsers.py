from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .models import Definition, ModInfo


_ACTIVE_MOD_RE = re.compile(r"^\s*mod\s*=\s*(.+?)\s*,?\s*$", re.IGNORECASE)
_ACTIVE_MAP_RE = re.compile(r"^\s*map\s*=\s*(.+?)\s*,?\s*$", re.IGNORECASE)
_INFO_LINE_RE = re.compile(r"^\s*([^#=]+?)\s*=\s*(.*?)\s*$")
_DEFINITION_RE = re.compile(
    r"^\s*(item|craftrecipe|recipe|vehicle|template|evolvedrecipe|fixing)\s+"
    r"(?:\"([^\"]+)\"|([^{\r\n]+?))\s*\{",
    re.IGNORECASE | re.MULTILINE,
)
_MODULE_RE = re.compile(
    r"^\s*module\s+([^\s{]+)\s*\{",
    re.IGNORECASE | re.MULTILINE,
)
_MAP_CELL_RE = re.compile(r"(?<!\d)(-?\d+)_(-?\d+)\.(?:lotheader|bin)$", re.IGNORECASE)


def parse_active_mods(path: Path) -> list[str]:
    mods, _ = parse_active_profile(path)
    return mods


def parse_active_profile(path: Path) -> tuple[list[str], list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Active mod profile not found: {path}")

    mods: list[str] = []
    maps: list[str] = []
    section: str | None = None
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if line.lower() == "mods":
            section = "mods"
            continue
        if line.lower() == "maps":
            section = "maps"
            continue
        if line == "}":
            section = None
            continue
        match = _ACTIVE_MOD_RE.match(raw_line) if section == "mods" else None
        if match:
            value = match.group(1).strip()
            if value:
                mods.append(value)
        map_match = _ACTIVE_MAP_RE.match(raw_line) if section == "maps" else None
        if map_match:
            value = map_match.group(1).strip()
            if value:
                maps.append(value)
    return mods, maps


def _split_values(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        for part in re.split(r"[,;]", value):
            cleaned = part.strip().lstrip("\\")
            if cleaned and cleaned not in result:
                result.append(cleaned)
    return result


def parse_mod_info(path: Path, workshop_id: str | None = None) -> ModInfo | None:
    raw: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _INFO_LINE_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        raw.setdefault(key, []).append(value)

    def first(*keys: str) -> str | None:
        for key in keys:
            values = raw.get(key)
            if values:
                return values[-1]
        return None

    mod_id = first("id")
    if not mod_id:
        return None

    return ModInfo(
        mod_id=mod_id,
        name=first("name") or mod_id,
        root=path.parent,
        info_path=path,
        workshop_id=workshop_id,
        author=first("author"),
        description=first("description"),
        mod_version=first("modversion", "version"),
        version_min=first("versionmin"),
        version_max=first("versionmax"),
        requires=_split_values(raw.get("require", []) + raw.get("requires", [])),
        load_after=_split_values(
            raw.get("loadmodafter", [])
            + raw.get("loadafter", [])
            + raw.get("load_after", [])
        ),
        load_before=_split_values(
            raw.get("loadmodbefore", [])
            + raw.get("loadbefore", [])
            + raw.get("load_before", [])
        ),
        incompatible=_split_values(
            raw.get("incompatible", []) + raw.get("incompatiblemods", [])
        ),
        raw=raw,
    )


def strip_script_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\r\n]*", "", text)
    return text


def _matching_brace(text: str, opening: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text)


def parse_script_definitions(path: Path, relative_path: str) -> list[Definition]:
    text = strip_script_comments(
        path.read_text(encoding="utf-8-sig", errors="replace")
    )
    records: list[Definition] = []
    covered: list[tuple[int, int]] = []

    for module_match in _MODULE_RE.finditer(text):
        opening = text.find("{", module_match.start())
        closing = _matching_brace(text, opening)
        module_name = module_match.group(1)
        covered.append((module_match.start(), closing))
        body = text[opening + 1 : closing]
        for match in _DEFINITION_RE.finditer(body):
            name = match.group(2) or match.group(3)
            records.append(
                Definition(
                    kind=match.group(1).lower(),
                    identifier=f"{module_name}.{name}",
                    file=relative_path,
                )
            )

    for match in _DEFINITION_RE.finditer(text):
        if any(start <= match.start() <= end for start, end in covered):
            continue
        name = match.group(2) or match.group(3)
        records.append(
            Definition(
                kind=match.group(1).lower(),
                identifier=name,
                file=relative_path,
            )
        )
    return records


def map_cell_from_path(path: Path) -> str | None:
    match = _MAP_CELL_RE.search(path.name)
    if not match:
        return None
    return f"{match.group(1)}_{match.group(2)}"


def parse_server_ini(path: Path) -> tuple[list[str], list[str]]:
    workshop_items: list[str] = []
    mods: list[str] = []
    if not path.is_file():
        return workshop_items, mods
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if raw_line.startswith("WorkshopItems="):
            workshop_items = [
                value.strip()
                for value in raw_line.partition("=")[2].split(";")
                if value.strip()
            ]
        elif raw_line.startswith("Mods="):
            mods = [
                value.strip()
                for value in raw_line.partition("=")[2].split(";")
                if value.strip()
            ]
    return workshop_items, mods
