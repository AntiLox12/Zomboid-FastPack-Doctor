from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


def _bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def write_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _finding_rows(report: dict[str, Any]) -> str:
    rows = []
    for finding in report["findings"]:
        mods = ", ".join(finding.get("mods", []))
        rows.append(
            "<tr>"
            f"<td><span class='severity {html.escape(finding['severity'])}'>"
            f"{html.escape(finding['severity'])}</span></td>"
            f"<td>{html.escape(finding['code'])}</td>"
            f"<td>{html.escape(finding['message'])}</td>"
            f"<td>{html.escape(mods)}</td>"
            "</tr>"
        )
    return "\n".join(rows) or "<tr><td colspan='4'>No findings.</td></tr>"


def _mod_rows(report: dict[str, Any]) -> str:
    rows = []
    for mod in sorted(report["mods"], key=lambda item: item["total_bytes"], reverse=True):
        info = mod["mod"]
        rows.append(
            "<tr>"
            f"<td>{mod['active_index'] + 1}</td>"
            f"<td><strong>{html.escape(info['name'])}</strong>"
            f"<small>{html.escape(info['mod_id'])}</small></td>"
            f"<td>{html.escape(mod['role'])}</td>"
            f"<td>{mod['file_count']:,}</td>"
            f"<td>{_bytes(mod['total_bytes'])}</td>"
            f"<td>{mod['lua_files']:,}</td>"
            f"<td>{mod['script_files']:,}</td>"
            f"<td>{mod['texture_files']:,}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _change_rows(report: dict[str, Any]) -> str:
    rows = []
    for change in report.get("changes", []):
        rows.append(
            "<tr>"
            f"<td>{html.escape(change['mod_id'])}</td>"
            f"<td>{html.escape(change['status'])}</td>"
            f"<td>{change.get('file_delta', '')}</td>"
            f"<td>{_bytes(change.get('byte_delta', 0)) if 'byte_delta' in change else ''}</td>"
            "</tr>"
        )
    return "\n".join(rows) or "<tr><td colspan='4'>No baseline changes.</td></tr>"


def _runtime_rows(report: dict[str, Any]) -> str:
    runtime = report.get("runtime", {})
    if not runtime.get("available"):
        return "<tr><td colspan='5'>No in-game runtime report found.</td></tr>"
    rows = []
    callbacks = sorted(
        runtime.get("callbacks", []),
        key=lambda row: row.get("totalMs", 0),
        reverse=True,
    )
    for row in callbacks:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('owner', 'unknown')))}</td>"
            f"<td>{html.escape(str(row.get('event', 'callback')))}</td>"
            f"<td>{int(row.get('calls', 0)):,}</td>"
            f"<td>{int(row.get('totalMs', 0)):,} ms</td>"
            f"<td>{int(row.get('maxMs', 0)):,} ms</td>"
            "</tr>"
        )
    return "\n".join(rows) or (
        "<tr><td colspan='5'>Runtime report exists, but no compatible callbacks "
        "were profiled.</td></tr>"
    )


def _runtime_owner_rows(report: dict[str, Any]) -> str:
    runtime = report.get("runtime", {})
    if not runtime.get("available"):
        return "<tr><td colspan='4'>No in-game runtime report found.</td></tr>"
    owners: dict[str, dict[str, int]] = {}
    for row in runtime.get("callbacks", []):
        owner = str(row.get("owner", "unknown"))
        summary = owners.setdefault(
            owner,
            {"calls": 0, "totalMs": 0, "maxMs": 0},
        )
        summary["calls"] += int(row.get("calls", 0))
        summary["totalMs"] += int(row.get("totalMs", 0))
        summary["maxMs"] = max(summary["maxMs"], int(row.get("maxMs", 0)))
    rows = []
    for owner, summary in sorted(
        owners.items(),
        key=lambda item: item[1]["totalMs"],
        reverse=True,
    ):
        rows.append(
            "<tr>"
            f"<td>{html.escape(owner)}</td>"
            f"<td>{summary['calls']:,}</td>"
            f"<td>{summary['totalMs']:,} ms</td>"
            f"<td>{summary['maxMs']:,} ms</td>"
            "</tr>"
        )
    return "\n".join(rows) or (
        "<tr><td colspan='4'>No compatible mod callbacks were profiled.</td></tr>"
    )


def _console_rows(report: dict[str, Any]) -> str:
    console = report.get("console", {})
    if not console.get("available"):
        return "<tr><td>No console.txt was available.</td></tr>"
    errors = console.get("recent_errors", [])
    if not errors:
        return "<tr><td>No matching error lines were found.</td></tr>"
    return "\n".join(
        f"<tr><td><code>{html.escape(str(line))}</code></td></tr>"
        for line in errors[-50:]
    )


def write_html(report: dict[str, Any], path: Path) -> None:
    totals = report["totals"]
    findings = totals.get("findings", {})
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FastPack Report</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101315; --panel: #191e22; --line: #303940;
  --text: #e8edf0; --muted: #9caab3; --accent: #e7b657;
  --error: #ff6b6b; --warning: #ffd166; --info: #69b7ff;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1500px, 96vw); margin: 28px auto 60px; }}
h1 {{ margin-bottom: 4px; color: var(--accent); }}
h2 {{ margin-top: 32px; }}
.muted, small {{ color: var(--muted); }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px; margin: 22px 0; }}
.card {{ background: var(--panel); border: 1px solid var(--line);
  border-radius: 8px; padding: 14px; }}
.card strong {{ display: block; font-size: 24px; }}
.table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); }}
th, td {{ padding: 9px 11px; text-align: left; border-bottom: 1px solid var(--line);
  vertical-align: top; }}
th {{ position: sticky; top: 0; background: #22292e; }}
td small {{ display: block; }}
.severity {{ font-weight: 700; text-transform: uppercase; }}
.severity.error {{ color: var(--error); }}
.severity.warning {{ color: var(--warning); }}
.severity.info {{ color: var(--info); }}
code {{ color: #a8d8ff; }}
</style>
</head>
<body><main>
<h1>FastPack Report</h1>
<div class="muted">Generated {html.escape(report['generated_at'])} ·
Build {html.escape(report['game_version'])} ·
<code>{html.escape(report['profile_hash'][:16])}</code></div>
<section class="cards">
  <div class="card"><span>Active mods</span><strong>{totals['active_entries']:,}</strong></div>
  <div class="card"><span>Files</span><strong>{totals['files']:,}</strong></div>
  <div class="card"><span>Total size</span><strong>{_bytes(totals['bytes'])}</strong></div>
  <div class="card"><span>Lua files</span><strong>{totals['lua_files']:,}</strong></div>
  <div class="card"><span>Errors</span><strong>{findings.get('error', 0):,}</strong></div>
  <div class="card"><span>Warnings</span><strong>{findings.get('warning', 0):,}</strong></div>
</section>
<h2>Diagnostics</h2>
<div class="table-wrap"><table>
<thead><tr><th>Severity</th><th>Code</th><th>Message</th><th>Mods</th></tr></thead>
<tbody>{_finding_rows(report)}</tbody>
</table></div>
<h2>Mods by size</h2>
<div class="table-wrap"><table>
<thead><tr><th>Order</th><th>Mod</th><th>Role</th><th>Files</th><th>Size</th>
<th>Lua</th><th>Scripts</th><th>Textures</th></tr></thead>
<tbody>{_mod_rows(report)}</tbody>
</table></div>
<h2>Changes from baseline</h2>
<div class="table-wrap"><table>
<thead><tr><th>Mod</th><th>Status</th><th>File delta</th><th>Size delta</th></tr></thead>
<tbody>{_change_rows(report)}</tbody>
</table></div>
<h2>In-game callback profile</h2>
<div class="table-wrap"><table>
<thead><tr><th>Mod / owner</th><th>Calls</th><th>Total</th><th>Max callback</th></tr></thead>
<tbody>{_runtime_owner_rows(report)}</tbody>
</table></div>
<h2>Callback details</h2>
<div class="table-wrap"><table>
<thead><tr><th>Owner</th><th>Event</th><th>Calls</th><th>Total</th><th>Max</th></tr></thead>
<tbody>{_runtime_rows(report)}</tbody>
</table></div>
<h2>Recent console errors</h2>
<div class="table-wrap"><table>
<thead><tr><th>Last matching lines from console.txt</th></tr></thead>
<tbody>{_console_rows(report)}</tbody>
</table></div>
</main></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


def build_safe_mode_profile(report: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    mods_by_id = {row["mod"]["mod_id"]: row for row in report["mods"]}

    def resolve_reference(reference: str) -> str:
        if reference in mods_by_id:
            return reference
        if "/" in reference:
            suffix = reference.split("/", 1)[1]
            if suffix in mods_by_id:
                return suffix
        return reference

    optional_roles = {"texture_pack", "sound_pack"}
    disabled: set[str] = {
        mod_id
        for mod_id, row in mods_by_id.items()
        if row["role"] in optional_roles
    }
    cosmetic_patterns = (
        r"\b4k\b",
        r"\bhd\b.*\btexture",
        r"\bretexture\b",
        r"\bcosmetic",
        r"\bhair\b",
        r"\bmakeup\b",
        r"\breshade\b",
        r"\bshader",
        r"\bblood effect",
    )
    for mod_id, row in mods_by_id.items():
        if row["role"] in {"framework", "map"}:
            continue
        haystack = f"{mod_id} {row['mod']['name']}".lower()
        if any(re.search(pattern, haystack) for pattern in cosmetic_patterns):
            disabled.add(mod_id)

    changed = True
    while changed:
        changed = False
        for mod_id, row in mods_by_id.items():
            if mod_id in disabled:
                continue
            for required in row["mod"].get("requires", []):
                required_id = resolve_reference(required)
                if required_id in disabled:
                    disabled.remove(required_id)
                    changed = True

    kept_tokens = [
        token
        for token in report["active_order"]
        if resolve_reference(token) not in disabled
    ]
    lines = ["VERSION = 1,", "", "mods", "{"]
    lines.extend(f"    mod = {token}," for token in kept_tokens)
    lines.extend(["}", "", "maps", "{", "}", ""])
    if report.get("active_maps"):
        lines = ["VERSION = 1,", "", "mods", "{"]
        lines.extend(f"    mod = {token}," for token in kept_tokens)
        lines.extend(["}", "", "maps", "{"])
        lines.extend(f"    map = {value}," for value in report["active_maps"])
        lines.extend(["}", ""])
    summary = {
        "kept": len(kept_tokens),
        "disabled": len(disabled),
        "disabled_mods": sorted(disabled),
        "unresolved_kept": [
            token
            for token in report["active_order"]
            if resolve_reference(token) not in mods_by_id
        ],
        "note": "Unresolved entries are kept. Review before replacing any live profile.",
    }
    return "\n".join(lines), summary
