ZOMBOID FASTPACK DOCTOR - WINDOWS COMPANION 0.1.0

QUICK START

Double-click RUN_FASTPACK_DOCTOR.bat.

The scanner automatically detects:
- Steam and Project Zomboid;
- Workshop content for app 108600;
- the active Build 42 mod profile;
- local mods;
- console.txt;
- the FastPack runtime report.

Results are written to:
outputs\fastpack-report\

Open fastpack-report.html in a browser.

The generated fastpack-safe-mode.txt is only a diagnostic suggestion. The
program never replaces your active mod profile automatically.

COMMAND LINE

FastPackDoctor.exe scan --safe-mode
FastPackDoctor.exe scan --baseline "path\to\fastpack-report.json"
FastPackDoctor.exe scan --server-ini "path\to\servertest.ini"

Project and updates:
https://github.com/AntiLox12/Zomboid-FastPack-Doctor

