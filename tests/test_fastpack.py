from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))

from fastpack_doctor.models import ScanConfig  # noqa: E402
from fastpack_doctor.discovery import _layout_version, resolve_active_mod  # noqa: E402
from fastpack_doctor.parsers import (  # noqa: E402
    parse_active_mods,
    parse_active_profile,
    parse_mod_info,
    parse_script_definitions,
)
from fastpack_doctor.report import build_safe_mode_profile  # noqa: E402
from fastpack_doctor.scanner import scan  # noqa: E402


class ParserTests(unittest.TestCase):
    def test_active_profile_keeps_spaces_and_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "default.txt"
            profile.write_text(
                """VERSION = 1,
mods
{
    mod = tsarslib,
    mod = GanydeBielovzki's Frockin Splendor! Vol.2,
    mod = 1299328280/ToadTraits,
}
maps
{
}
""",
                encoding="utf-8",
            )
            self.assertEqual(
                parse_active_mods(profile),
                [
                    "tsarslib",
                    "GanydeBielovzki's Frockin Splendor! Vol.2",
                    "1299328280/ToadTraits",
                ],
            )
            _, maps = parse_active_profile(profile)
            self.assertEqual(maps, [])

    def test_mod_info_fields_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            info_path = Path(directory) / "mod.info"
            info_path.write_text(
                """name=Example
id=ExampleMod
require=FrameworkA, FrameworkB
loadModAfter=ContentBase
versionMin=42.19
""",
                encoding="utf-8",
            )
            info = parse_mod_info(info_path, "123")
            self.assertIsNotNone(info)
            assert info is not None
            self.assertEqual(info.requires, ["FrameworkA", "FrameworkB"])
            self.assertEqual(info.load_after, ["ContentBase"])
            self.assertEqual(info.source_key, "123/ExampleMod")

    def test_active_id_with_slash_is_resolved_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            info_path = Path(directory) / "mod.info"
            info_path.write_text(
                "name=Traits\nid=1299328280/ToadTraits\n",
                encoding="utf-8",
            )
            info = parse_mod_info(info_path, "1299328280")
            self.assertEqual(info.mod_id if info else None, "1299328280/ToadTraits")

    def test_local_provider_wins_over_workshop_without_explicit_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            local_path = base / "local" / "42.0" / "mod.info"
            workshop_path = base / "workshop" / "42.19" / "mod.info"
            local_path.parent.mkdir(parents=True)
            workshop_path.parent.mkdir(parents=True)
            local_path.write_text("name=Local\nid=Shared\n", encoding="utf-8")
            workshop_path.write_text("name=Workshop\nid=Shared\n", encoding="utf-8")
            local = parse_mod_info(local_path)
            workshop = parse_mod_info(workshop_path, "123")
            assert local is not None and workshop is not None
            resolved = resolve_active_mod(
                "Shared",
                {"Shared": [workshop, local]},
                "42.19",
            )
            self.assertEqual(resolved.name if resolved else None, "Local")

    def test_semantic_patch_version_matches_short_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old_path = base / "42.18" / "mod.info"
            current_path = base / "42.19.0" / "mod.info"
            old_path.parent.mkdir()
            current_path.parent.mkdir()
            old_path.write_text("name=Old\nid=Shared\n", encoding="utf-8")
            current_path.write_text("name=Current\nid=Shared\n", encoding="utf-8")
            old = parse_mod_info(old_path)
            current = parse_mod_info(current_path)
            assert old is not None and current is not None
            resolved = resolve_active_mod(
                "Shared",
                {"Shared": [old, current]},
                "42.19",
            )
            self.assertEqual(resolved.name if resolved else None, "Current")

    def test_workshop_id_is_not_treated_as_layout_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = (
                Path(directory)
                / "3402491515"
                / "mods"
                / "Example"
                / "common"
                / "mod.info"
            )
            path.parent.mkdir(parents=True)
            path.write_text("name=Example\nid=Example\n", encoding="utf-8")
            info = parse_mod_info(path, "3402491515")
            assert info is not None
            self.assertEqual(_layout_version(info), ())

    def test_script_definition_parser_uses_module_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "items.txt"
            script.write_text(
                """module Base
{
    item TestItem
    {
        Weight = 1.0,
    }
    recipe "Make Test"
    {
        TestItem,
    }
}
""",
                encoding="utf-8",
            )
            records = parse_script_definitions(script, "media/scripts/items.txt")
            self.assertEqual(
                [(row.kind, row.identifier) for row in records],
                [("item", "Base.TestItem"), ("recipe", "Base.Make Test")],
            )

    def test_unquoted_build_42_craft_recipe_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "recipes.txt"
            script.write_text(
                """module Base
{
    craftRecipe Make a Better Hammer
    {
    }
}
""",
                encoding="utf-8",
            )
            records = parse_script_definitions(script, "media/scripts/recipes.txt")
            self.assertEqual(
                [(row.kind, row.identifier) for row in records],
                [("craftrecipe", "Base.Make a Better Hammer")],
            )


class ScanTests(unittest.TestCase):
    def _write_mod(
        self,
        local_mods: Path,
        folder: str,
        mod_id: str,
        requires: str = "",
        texture_only: bool = False,
    ) -> None:
        root = local_mods / folder / "42.0"
        root.mkdir(parents=True)
        require_line = f"require={requires}\n" if requires else ""
        (root / "mod.info").write_text(
            f"name={folder}\nid={mod_id}\nversionMin=42.19\n{require_line}",
            encoding="utf-8",
        )
        if texture_only:
            texture = root / "media" / "textures" / f"{folder}.png"
            texture.parent.mkdir(parents=True)
            texture.write_bytes(b"\x89PNG" + b"x" * 100)
        else:
            script = root / "media" / "scripts" / "items.txt"
            script.parent.mkdir(parents=True)
            script.write_text(
                """module Base
{
    item SharedItem
    {
        Weight = 1.0,
    }
}
""",
                encoding="utf-8",
            )

    def test_scan_detects_dependency_order_and_duplicate_definition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            local_mods = base / "mods"
            local_mods.mkdir()
            self._write_mod(local_mods, "Dependent", "Dependent", "Framework")
            self._write_mod(local_mods, "Framework", "Framework")
            active = local_mods / "default.txt"
            active.write_text(
                """VERSION = 1,
mods
{
    mod = Dependent,
    mod = Framework,
}
maps
{
}
""",
                encoding="utf-8",
            )
            config = ScanConfig(
                active_file=active,
                local_mods=local_mods,
                workshop_roots=[],
                output_dir=base / "out",
                console_file=None,
            )
            report = scan(config)
            codes = [finding["code"] for finding in report["findings"]]
            self.assertIn("REQUIREMENT_AFTER_DEPENDENT", codes)
            self.assertIn("DUPLICATE_DEFINITION", codes)
            self.assertEqual(report["totals"]["resolved_mods"], 2)
            self.assertNotIn(
                "localization",
                {row["role"] for row in report["mods"]},
            )

    def test_safe_mode_drops_texture_pack_without_modifying_report(self) -> None:
        report = {
            "active_order": ["Core", "Pretty4K"],
            "active_maps": ["Muldraugh, KY"],
            "mods": [
                {
                    "mod": {"mod_id": "Core", "name": "Core", "requires": []},
                    "role": "framework",
                },
                {
                    "mod": {
                        "mod_id": "Pretty4K",
                        "name": "Pretty 4K Retexture",
                        "requires": [],
                    },
                    "role": "texture_pack",
                },
            ],
        }
        profile, summary = build_safe_mode_profile(report)
        self.assertIn("mod = Core,", profile)
        self.assertNotIn("mod = Pretty4K,", profile)
        self.assertIn("map = Muldraugh, KY,", profile)
        self.assertEqual(summary["disabled_mods"], ["Pretty4K"])

    def test_safe_mode_handles_real_mod_id_containing_slash(self) -> None:
        report = {
            "active_order": ["123/TexturePack"],
            "active_maps": [],
            "mods": [
                {
                    "mod": {
                        "mod_id": "123/TexturePack",
                        "name": "Texture Pack",
                        "requires": [],
                    },
                    "role": "texture_pack",
                }
            ],
        }
        profile, summary = build_safe_mode_profile(report)
        self.assertNotIn("mod = 123/TexturePack,", profile)
        self.assertEqual(summary["disabled_mods"], ["123/TexturePack"])

    def test_dependency_with_slash_id_is_not_shortened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            local_mods = base / "mods"
            local_mods.mkdir()
            self._write_mod(
                local_mods,
                "Traits",
                "1299328280/ToadTraits",
            )
            self._write_mod(
                local_mods,
                "Addon",
                "Addon",
                "1299328280/ToadTraits",
            )
            active = local_mods / "default.txt"
            active.write_text(
                """VERSION = 1,
mods
{
    mod = 1299328280/ToadTraits,
    mod = Addon,
}
maps
{
}
""",
                encoding="utf-8",
            )
            report = scan(
                ScanConfig(
                    active_file=active,
                    local_mods=local_mods,
                    workshop_roots=[],
                    output_dir=base / "out",
                )
            )
            missing = [
                finding
                for finding in report["findings"]
                if finding["code"] == "MISSING_REQUIREMENT"
            ]
            self.assertEqual(missing, [])

    def test_server_ini_mismatch_is_reported_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            local_mods = base / "mods"
            local_mods.mkdir()
            self._write_mod(local_mods, "Core", "Core")
            active = local_mods / "default.txt"
            active.write_text(
                "VERSION = 1,\nmods\n{\n    mod = Core,\n}\nmaps\n{\n}\n",
                encoding="utf-8",
            )
            server_ini = base / "server.ini"
            server_ini.write_text(
                "WorkshopItems=999\nMods=Other\n",
                encoding="utf-8",
            )
            report = scan(
                ScanConfig(
                    active_file=active,
                    local_mods=local_mods,
                    workshop_roots=[],
                    output_dir=base / "out",
                    server_ini=server_ini,
                )
            )
            codes = {finding["code"] for finding in report["findings"]}
            self.assertIn("SERVER_MODS_MISMATCH", codes)
            self.assertIn("SERVER_WORKSHOP_ORDER_MISMATCH", codes)

    def test_common_metadata_includes_compatible_version_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            local_mods = base / "mods"
            common = local_mods / "Layered" / "common"
            version = local_mods / "Layered" / "42.19.0"
            common.mkdir(parents=True)
            (common / "mod.info").write_text(
                "name=Layered\nid=Layered\n",
                encoding="utf-8",
            )
            script = version / "media" / "scripts" / "items.txt"
            script.parent.mkdir(parents=True)
            script.write_text(
                """module Base
{
    item LayeredItem
    {
    }
}
""",
                encoding="utf-8",
            )
            legacy_script = (
                local_mods
                / "Layered"
                / "media"
                / "scripts"
                / "legacy-items.txt"
            )
            legacy_script.parent.mkdir(parents=True)
            legacy_script.write_text(
                """module Base
{
    item LegacyItem
    {
    }
}
""",
                encoding="utf-8",
            )
            active = local_mods / "default.txt"
            active.write_text(
                "VERSION = 1,\nmods\n{\n    mod = Layered,\n}\nmaps\n{\n}\n",
                encoding="utf-8",
            )
            report = scan(
                ScanConfig(
                    active_file=active,
                    local_mods=local_mods,
                    workshop_roots=[],
                    output_dir=base / "out",
                    game_version="42.19",
                )
            )
            row = report["mods"][0]
            self.assertEqual(row["script_files"], 1)
            self.assertEqual(row["definitions"]["item"], 1)


if __name__ == "__main__":
    unittest.main()
