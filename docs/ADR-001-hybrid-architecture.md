# ADR-001: Hybrid Lua Mod and External Companion

**Status:** Accepted
**Date:** 2026-06-13
**Deciders:** Project maintainer

## Context

Project Zomboid loads mod files before a normal Lua mod can inspect or alter
most of the loader. A Lua-only implementation cannot accurately inventory the
Workshop tree, compare historical snapshots, or prevent early loader work.
It can still measure cooperative callbacks, expose UI, and spread compatible
initialization work across frames after world load.

## Decision

FastPack Doctor is split into two components:

1. A standard-library Python companion scans files before launch and produces
   versioned JSON/HTML reports and safe-mode plans.
2. A Build 42 Lua mod exposes `FastPack.defer`, profiles handlers registered
   through its API, and writes a small runtime report.

The JSON report is the integration contract. The Lua component does not patch
Java classes in the default distribution.

## Options Considered

### Lua-only

| Dimension | Assessment |
|---|---|
| Installation | Easy |
| Pre-launch visibility | Poor |
| File-system analysis | Limited |
| Runtime profiling | Moderate |

### Java patcher

| Dimension | Assessment |
|---|---|
| Installation | Hard |
| Pre-launch visibility | Moderate |
| Profiling depth | High |
| Version fragility | High |

### Hybrid Lua and companion

| Dimension | Assessment |
|---|---|
| Installation | Moderate |
| Pre-launch visibility | High |
| Runtime profiling | Moderate |
| Version fragility | Low |

## Consequences

- Deep per-call Lua profiling remains optional future work.
- Cooperative mods can improve perceived startup through `FastPack.defer`.
- Reports remain useful even when the in-game mod is disabled.
- The scanner must treat findings as diagnostics, not automatically rewrite a
  working load order.

