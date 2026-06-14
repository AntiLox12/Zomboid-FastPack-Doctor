# FastPack Modder API

FastPack's runtime API is cooperative. It cannot interrupt a callback that
blocks for 200 ms. A deferred task must do a bounded unit of work and return
`true` only when complete.

## Deferred initialization

```lua
local index = 1

FastPack.defer("Build catalog", function()
    for _ = 1, 25 do
        if index > #MyMod.records then
            return true
        end
        MyMod.indexRecord(MyMod.records[index])
        index = index + 1
    end
    return false
end, {
    owner = "MyMod",
    stage = "after_world_load",
    budgetMs = 5,
})
```

Available stages:

- `immediate`
- `main_menu`
- `after_world_load`
- `after_player_create`

The global queue spends at most 6 ms per `OnTick` by default. A task that
exceeds its declared budget is reported but cannot be forcibly stopped.

## Profile a callback

```lua
FastPack.addEvent("OnFillInventoryObjectContextMenu", "MyMod", function(player, context, items)
    MyMod.addEntries(player, context, items)
end)
```

Or wrap a callback for an API that is not an `Events` entry:

```lua
local wrapped = FastPack.wrap("MyMod", "CustomHook", MyMod.onCustomHook)
ThirdPartyAPI.addHook(wrapped)
```

Only callbacks registered through these functions are measured by the
standard Lua distribution. Return values are preserved, and callback errors
are recorded before being rethrown so FastPack does not change failure
semantics.

## Runtime report

`FastPack.writeRuntimeReport()` writes
`Zomboid/Lua/FastPackDoctor/runtime.json`.

The report is refreshed when a runnable deferred queue drains. Failed tasks
are written separately from completed tasks.
