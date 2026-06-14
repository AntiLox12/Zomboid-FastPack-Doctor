from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ModInfo:
    mod_id: str
    name: str
    root: Path
    info_path: Path
    workshop_id: str | None = None
    author: str | None = None
    description: str | None = None
    mod_version: str | None = None
    version_min: str | None = None
    version_max: str | None = None
    requires: list[str] = field(default_factory=list)
    load_after: list[str] = field(default_factory=list)
    load_before: list[str] = field(default_factory=list)
    incompatible: list[str] = field(default_factory=list)
    raw: dict[str, list[str]] = field(default_factory=dict)

    @property
    def source_key(self) -> str:
        if self.workshop_id:
            return f"{self.workshop_id}/{self.mod_id}"
        return self.mod_id


@dataclass(slots=True)
class Definition:
    kind: str
    identifier: str
    file: str


@dataclass(slots=True)
class ModStats:
    mod: ModInfo
    active_index: int
    file_count: int = 0
    total_bytes: int = 0
    lua_files: int = 0
    lua_bytes: int = 0
    script_files: int = 0
    texture_files: int = 0
    texture_bytes: int = 0
    sound_files: int = 0
    sound_bytes: int = 0
    model_files: int = 0
    model_bytes: int = 0
    translation_files: int = 0
    definitions: dict[str, int] = field(default_factory=dict)
    definition_records: list[Definition] = field(default_factory=list)
    map_cells: list[str] = field(default_factory=list)
    relative_assets: list[str] = field(default_factory=list)
    role: str = "content"
    warnings: list[str] = field(default_factory=list)
    scan_error: str | None = None

    def to_dict(self, include_records: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data["mod"]["root"] = str(self.mod.root)
        data["mod"]["info_path"] = str(self.mod.info_path)
        if not include_records:
            data.pop("definition_records", None)
            data.pop("relative_assets", None)
        return data


@dataclass(slots=True)
class Finding:
    severity: str
    code: str
    message: str
    mods: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScanConfig:
    active_file: Path
    local_mods: Path
    workshop_roots: list[Path]
    output_dir: Path
    console_file: Path | None = None
    runtime_file: Path | None = None
    server_ini: Path | None = None
    baseline_file: Path | None = None
    game_version: str = "42.19"
    top: int = 25
