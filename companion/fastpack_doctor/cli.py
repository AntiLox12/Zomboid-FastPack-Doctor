from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .discovery import (
    default_active_file,
    default_console_file,
    default_local_mods,
    default_runtime_file,
    discover_steam_root,
    discover_workshop_roots,
)
from .models import ScanConfig
from .report import build_safe_mode_profile, write_html, write_json
from .scanner import scan


def _path(value: str | None) -> Path | None:
    return Path(value).expanduser().resolve() if value else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fastpack",
        description="Diagnose large Project Zomboid Build 42 modpacks.",
    )
    subparsers = parser.add_subparsers(dest="command")
    scan_parser = subparsers.add_parser("scan", help="Scan an active mod profile.")
    scan_parser.add_argument("--steam", help="Steam installation directory.")
    scan_parser.add_argument(
        "--workshop",
        action="append",
        default=[],
        help="Additional Workshop content/108600 directory. Repeatable.",
    )
    scan_parser.add_argument("--local-mods", help="Zomboid local mods directory.")
    scan_parser.add_argument("--active-file", help="Active mods profile.")
    scan_parser.add_argument("--console", help="Project Zomboid console.txt.")
    scan_parser.add_argument("--runtime", help="FastPack in-game runtime JSON.")
    scan_parser.add_argument("--server-ini", help="Optional dedicated-server INI.")
    scan_parser.add_argument("--baseline", help="Previous FastPack JSON report.")
    scan_parser.add_argument(
        "--output",
        default="outputs/fastpack-report",
        help="Output directory.",
    )
    scan_parser.add_argument("--game-version", default="42.19")
    scan_parser.add_argument("--top", type=int, default=25)
    scan_parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Also create a conservative diagnostic profile.",
    )
    return parser


def _scan_command(args: argparse.Namespace) -> int:
    steam = discover_steam_root(_path(args.steam))
    workshop_roots = [_path(value) for value in args.workshop]
    workshop_roots = [path for path in workshop_roots if path is not None]
    for path in discover_workshop_roots(steam):
        if path not in workshop_roots:
            workshop_roots.append(path)

    local_mods = _path(args.local_mods) or default_local_mods()
    active_file = _path(args.active_file) or default_active_file()
    console_file = _path(args.console) or default_console_file()
    runtime_file = _path(args.runtime) or default_runtime_file()
    server_ini = _path(args.server_ini)
    baseline_file = _path(args.baseline)
    output_dir = Path(args.output).expanduser().resolve()

    config = ScanConfig(
        active_file=active_file,
        local_mods=local_mods,
        workshop_roots=workshop_roots,
        output_dir=output_dir,
        console_file=console_file,
        runtime_file=runtime_file,
        server_ini=server_ini,
        baseline_file=baseline_file,
        game_version=args.game_version,
        top=max(1, args.top),
    )

    print(f"[FastPack] Active profile: {active_file}")
    print(f"[FastPack] Local mods: {local_mods}")
    print(f"[FastPack] Workshop roots: {len(workshop_roots)}")
    started = time.perf_counter()
    try:
        report = scan(config)
    except (FileNotFoundError, PermissionError) as exc:
        print(f"[FastPack] ERROR: {exc}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "fastpack-report.json"
    html_path = output_dir / "fastpack-report.html"
    write_json(report, json_path)
    write_html(report, html_path)

    if args.safe_mode:
        profile, summary = build_safe_mode_profile(report)
        (output_dir / "fastpack-safe-mode.txt").write_text(profile, encoding="utf-8")
        (output_dir / "fastpack-safe-mode.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    elapsed = time.perf_counter() - started
    totals = report["totals"]
    finding_counts = totals.get("findings", {})
    print(
        "[FastPack] "
        f"{totals['resolved_mods']}/{totals['active_entries']} mods, "
        f"{totals['files']:,} files, "
        f"{finding_counts.get('error', 0)} errors, "
        f"{finding_counts.get('warning', 0)} warnings in {elapsed:.1f}s"
    )
    print(f"[FastPack] JSON: {json_path}")
    print(f"[FastPack] HTML: {html_path}")
    return 1 if finding_counts.get("error", 0) else 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command in {None, "scan"}:
        if args.command is None:
            args = parser.parse_args(["scan", *(argv or [])])
        return _scan_command(args)
    parser.print_help()
    return 2
