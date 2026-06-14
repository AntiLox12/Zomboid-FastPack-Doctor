[h1]Zomboid FastPack Doctor[/h1]

Runtime diagnostics and a cooperative lazy-loading API for large
Project Zomboid Build 42 modpacks.

[h2]How to use[/h2]

1. Subscribe and enable Zomboid FastPack Doctor.
2. Load a world.
3. Open the pause menu, open the active mod list, and select FastPack Report.
4. Use the GitHub button for the full pre-launch Companion scanner.

[h2]Workshop mod vs Companion[/h2]

The Workshop subscription installs only the in-game component. Deep scans for
mod sizes, duplicate item/vehicle/recipe IDs, map overlaps, dependencies,
console errors, outdated layouts, safe-mode profiles, and HTML reports require
the free Windows Companion:

https://github.com/AntiLox12/Zomboid-FastPack-Doctor/releases/latest

[h2]Important limitation[/h2]

FastPack Doctor does not rewrite the native loader and does not promise fake
percentage speedups. Runtime profiling covers compatible callbacks registered
through the FastPack API.

