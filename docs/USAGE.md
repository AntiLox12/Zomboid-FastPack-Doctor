# Companion Usage

## Automatic scan

From the repository root:

```powershell
python .\companion\fastpack.py scan --safe-mode
```

On Windows, FastPack Doctor reads the Steam path from the registry and uses:

- `%USERPROFILE%\Zomboid\mods\default.txt`
- `%USERPROFILE%\Zomboid\mods`
- every detected Steam `workshop\content\108600` directory
- `%USERPROFILE%\Zomboid\console.txt`
- `%USERPROFILE%\Zomboid\Lua\FastPackDoctor\runtime.json`

Generated files:

- `fastpack-report.json`: machine-readable versioned profile
- `fastpack-report.html`: standalone report
- `fastpack-safe-mode.txt`: conservative candidate profile
- `fastpack-safe-mode.json`: list of disabled candidates

The safe-mode profile is never installed automatically.

## Explicit paths

```powershell
python .\companion\fastpack.py scan `
  --steam "D:\Programs\Steam" `
  --active-file "$env:USERPROFILE\Zomboid\mods\default.txt" `
  --output ".\outputs\my-pack"
```

## Compare after Workshop updates

```powershell
python .\companion\fastpack.py scan `
  --baseline ".\outputs\before\fastpack-report.json" `
  --output ".\outputs\after"
```

## Exit codes

- `0`: scan completed without error-level findings
- `1`: scan completed with error-level findings
- `2`: input or permission error
