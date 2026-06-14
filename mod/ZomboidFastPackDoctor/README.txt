Zomboid FastPack Doctor 0.1.0

Build 42.19+

This in-game component provides:
- cooperative deferred initialization through FastPack.defer;
- callback profiling through FastPack.wrap and FastPack.addEvent;
- a runtime report available from the pause-menu active mod list;
- Zomboid/Lua/FastPackDoctor/runtime.json for the companion scanner.

The external companion is required for pre-launch Workshop scans, duplicate
definitions, map overlaps, size reports, safe-mode profiles, and HTML output.
Download it from:
https://github.com/AntiLox12/Zomboid-FastPack-Doctor/releases/latest

FastPack Doctor does not patch the Java loader and does not automatically
profile callbacks from mods that do not opt in.
