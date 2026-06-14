FastPack = FastPack or {}

FastPack.VERSION = "0.1.0"
FastPack.PROJECT_URL = "https://github.com/AntiLox12/Zomboid-FastPack-Doctor"
FastPack.RELEASES_URL = FastPack.PROJECT_URL .. "/releases/latest"
FastPack.DEFAULT_FRAME_BUDGET_MS = 6
FastPack.DEFAULT_TASK_BUDGET_MS = 5
FastPack.REPORT_FILE = "FastPackDoctor/runtime.json"
FastPack.stages = FastPack.stages or {
    immediate = true,
    main_menu = false,
    after_world_load = false,
    after_player_create = false,
}
FastPack.queues = FastPack.queues or {}
FastPack.profile = FastPack.profile or {}
FastPack.completed = FastPack.completed or {}
FastPack.failed = FastPack.failed or {}
FastPack.warnings = FastPack.warnings or {}
FastPack.warningSet = FastPack.warningSet or {}
FastPack.startedAt = FastPack.startedAt or getTimestampMs()
FastPack.worldStartedAt = FastPack.worldStartedAt or nil
FastPack.playerCreatedAt = FastPack.playerCreatedAt or nil
FastPack.menuReachedAt = FastPack.menuReachedAt or nil
FastPack.tickInstalled = FastPack.tickInstalled or false

local function now()
    return getTimestampMs()
end

local function jsonEscape(value)
    local text = tostring(value or "")
    text = text:gsub("\\", "\\\\")
    text = text:gsub("\"", "\\\"")
    text = text:gsub("\r", "\\r")
    text = text:gsub("\n", "\\n")
    text = text:gsub("\t", "\\t")
    text = text:gsub("[%z\1-\31]", function(character)
        return string.format("\\u%04x", string.byte(character))
    end)
    return text
end

local function sortedKeys(source)
    local result = {}
    for key, _ in pairs(source or {}) do
        table.insert(result, key)
    end
    table.sort(result)
    return result
end

local function pack(...)
    return { n = select("#", ...), ... }
end

local function addWarning(message)
    local key = tostring(message)
    if FastPack.warningSet[key] then
        return
    end
    FastPack.warningSet[key] = true
    table.insert(FastPack.warnings, {
        timeMs = now() - FastPack.startedAt,
        message = key,
    })
    print("[FastPack] WARNING: " .. key)
end

local function taskQueue(stage)
    FastPack.queues[stage] = FastPack.queues[stage] or {}
    return FastPack.queues[stage]
end

local function normalizeOptions(options)
    options = options or {}
    return {
        stage = options.stage or "after_world_load",
        budgetMs = math.max(1, tonumber(options.budgetMs) or FastPack.DEFAULT_TASK_BUDGET_MS),
        owner = tostring(options.owner or "unknown"),
    }
end

function FastPack.defer(name, task, options)
    if type(task) ~= "function" then
        error("FastPack.defer requires a function for " .. tostring(name))
    end

    local normalized = normalizeOptions(options)
    local entry = {
        name = tostring(name or "unnamed"),
        owner = normalized.owner,
        stage = normalized.stage,
        budgetMs = normalized.budgetMs,
        task = task,
        runs = 0,
        totalMs = 0,
        maxMs = 0,
        queuedAt = now(),
    }
    table.insert(taskQueue(normalized.stage), entry)
    if FastPack.stages[normalized.stage] then
        FastPack.ensureTick()
    end
    return entry
end

function FastPack.deferIterator(name, iterator, options)
    return FastPack.defer(name, function()
        return iterator() == nil
    end, options)
end

function FastPack.setStageReady(stage)
    FastPack.stages[stage] = true
    if #(FastPack.queues[stage] or {}) > 0 then
        FastPack.ensureTick()
    end
end

function FastPack.getPendingCount()
    local count = 0
    for _, queue in pairs(FastPack.queues) do
        count = count + #queue
    end
    return count
end

function FastPack.hasRunnableTasks()
    for stage, queue in pairs(FastPack.queues) do
        if FastPack.stages[stage] and #queue > 0 then
            return true
        end
    end
    return false
end

function FastPack.getProfileRows()
    local rows = {}
    for _, key in ipairs(sortedKeys(FastPack.profile)) do
        table.insert(rows, FastPack.profile[key])
    end
    table.sort(rows, function(left, right)
        if left.totalMs == right.totalMs then
            return left.key < right.key
        end
        return left.totalMs > right.totalMs
    end)
    return rows
end

function FastPack.wrap(owner, eventName, callback)
    if type(callback) ~= "function" then
        error("FastPack.wrap requires a callback")
    end

    local key = tostring(owner or "unknown") .. ":" .. tostring(eventName or "callback")
    local row = FastPack.profile[key]
    if not row then
        row = {
            key = key,
            owner = tostring(owner or "unknown"),
            event = tostring(eventName or "callback"),
            calls = 0,
            totalMs = 0,
            maxMs = 0,
            errors = 0,
        }
        FastPack.profile[key] = row
    end

    return function(...)
        local started = now()
        local values = pack(pcall(callback, ...))
        local elapsed = math.max(0, now() - started)
        row.calls = row.calls + 1
        row.totalMs = row.totalMs + elapsed
        row.maxMs = math.max(row.maxMs, elapsed)
        if not values[1] then
            row.errors = row.errors + 1
            addWarning(key .. " failed: " .. tostring(values[2]))
            error(values[2], 0)
        end
        return unpack(values, 2, values.n)
    end
end

function FastPack.addEvent(eventName, owner, callback)
    local event = Events[eventName]
    if not event or not event.Add then
        error("Unknown Project Zomboid event: " .. tostring(eventName))
    end
    local wrapped = FastPack.wrap(owner, eventName, callback)
    event.Add(wrapped)
    return wrapped
end

local function executeEntry(entry)
    local started = now()
    local values = pack(pcall(entry.task, entry))
    local elapsed = math.max(0, now() - started)
    entry.runs = entry.runs + 1
    entry.totalMs = entry.totalMs + elapsed
    entry.maxMs = math.max(entry.maxMs, elapsed)

    if elapsed > entry.budgetMs and not entry.budgetWarned then
        entry.budgetWarned = true
        addWarning(
            entry.owner .. ":" .. entry.name .. " exceeded its cooperative budget ("
            .. tostring(elapsed) .. "ms > " .. tostring(entry.budgetMs) .. "ms)"
        )
    end
    if not values[1] then
        entry.error = tostring(values[2])
        addWarning(entry.owner .. ":" .. entry.name .. " failed: " .. entry.error)
        return true, true
    end

    local result = values[2]
    if result == true then
        return true, false
    end
    if type(result) == "function" then
        entry.task = result
    end
    return false, false
end

function FastPack.onTick()
    local frameStarted = now()
    local frameBudget = FastPack.DEFAULT_FRAME_BUDGET_MS
    local stageNames = sortedKeys(FastPack.queues)

    for _, stage in ipairs(stageNames) do
        if FastPack.stages[stage] then
            local queue = FastPack.queues[stage]
            while #queue > 0 and math.max(0, now() - frameStarted) < frameBudget do
                local entry = table.remove(queue, 1)
                local finished, failed = executeEntry(entry)
                if finished then
                    entry.completedAt = now()
                    if failed then
                        table.insert(FastPack.failed, entry)
                    else
                        table.insert(FastPack.completed, entry)
                    end
                else
                    table.insert(queue, entry)
                end
            end
        end
        if math.max(0, now() - frameStarted) >= frameBudget then
            break
        end
    end

    if not FastPack.hasRunnableTasks() then
        Events.OnTick.Remove(FastPack.onTick)
        FastPack.tickInstalled = false
        FastPack.writeRuntimeReport()
    end
end

function FastPack.ensureTick()
    if FastPack.tickInstalled then
        return
    end
    Events.OnTick.Add(FastPack.onTick)
    FastPack.tickInstalled = true
end

local function writeJsonArray(writer, rows, render)
    writer:write("[")
    for index, row in ipairs(rows) do
        if index > 1 then
            writer:write(",")
        end
        writer:write(render(row))
    end
    writer:write("]")
end

function FastPack.writeRuntimeReport()
    local writer = getFileWriter(FastPack.REPORT_FILE, true, false)
    if not writer then
        addWarning("Could not open " .. FastPack.REPORT_FILE)
        return false
    end

    writer:write("{")
    writer:write("\"schemaVersion\":1,")
    writer:write("\"toolVersion\":\"" .. jsonEscape(FastPack.VERSION) .. "\",")
    writer:write("\"generatedAtMs\":" .. tostring(now()) .. ",")
    writer:write("\"elapsedMs\":" .. tostring(now() - FastPack.startedAt) .. ",")
    writer:write("\"menuReachedMs\":" .. tostring(FastPack.menuReachedAt or 0) .. ",")
    writer:write("\"worldReachedMs\":" .. tostring(FastPack.worldStartedAt or 0) .. ",")
    writer:write("\"playerReachedMs\":" .. tostring(FastPack.playerCreatedAt or 0) .. ",")
    writer:write("\"pendingTasks\":" .. tostring(FastPack.getPendingCount()) .. ",")
    writer:write("\"activeMods\":")
    local activeMods = {}
    local activeModList = getActivatedMods()
    for index = 0, activeModList:size() - 1 do
        table.insert(activeMods, tostring(activeModList:get(index)))
    end
    writeJsonArray(writer, activeMods, function(modId)
        return "\"" .. jsonEscape(modId) .. "\""
    end)
    writer:write(",")

    writer:write("\"callbacks\":")
    writeJsonArray(writer, FastPack.getProfileRows(), function(row)
        return "{"
            .. "\"key\":\"" .. jsonEscape(row.key) .. "\","
            .. "\"owner\":\"" .. jsonEscape(row.owner) .. "\","
            .. "\"event\":\"" .. jsonEscape(row.event) .. "\","
            .. "\"calls\":" .. tostring(row.calls) .. ","
            .. "\"totalMs\":" .. tostring(row.totalMs) .. ","
            .. "\"maxMs\":" .. tostring(row.maxMs) .. ","
            .. "\"errors\":" .. tostring(row.errors)
            .. "}"
    end)
    writer:write(",\"completedTasks\":")
    writeJsonArray(writer, FastPack.completed, function(row)
        return "{"
            .. "\"name\":\"" .. jsonEscape(row.name) .. "\","
            .. "\"owner\":\"" .. jsonEscape(row.owner) .. "\","
            .. "\"stage\":\"" .. jsonEscape(row.stage) .. "\","
            .. "\"runs\":" .. tostring(row.runs) .. ","
            .. "\"totalMs\":" .. tostring(row.totalMs) .. ","
            .. "\"maxMs\":" .. tostring(row.maxMs)
            .. "}"
    end)
    writer:write(",\"failedTasks\":")
    writeJsonArray(writer, FastPack.failed, function(row)
        return "{"
            .. "\"name\":\"" .. jsonEscape(row.name) .. "\","
            .. "\"owner\":\"" .. jsonEscape(row.owner) .. "\","
            .. "\"stage\":\"" .. jsonEscape(row.stage) .. "\","
            .. "\"runs\":" .. tostring(row.runs) .. ","
            .. "\"totalMs\":" .. tostring(row.totalMs) .. ","
            .. "\"maxMs\":" .. tostring(row.maxMs) .. ","
            .. "\"error\":\"" .. jsonEscape(row.error) .. "\""
            .. "}"
    end)
    writer:write(",\"warnings\":")
    writeJsonArray(writer, FastPack.warnings, function(row)
        return "{"
            .. "\"timeMs\":" .. tostring(row.timeMs) .. ","
            .. "\"message\":\"" .. jsonEscape(row.message) .. "\""
            .. "}"
    end)
    writer:write("}")
    writer:close()
    return true
end

function FastPack.onMainMenuEnter()
    if not FastPack.menuReachedAt then
        FastPack.menuReachedAt = now() - FastPack.startedAt
    end
    FastPack.setStageReady("main_menu")
end

function FastPack.onGameStart()
    if not FastPack.worldStartedAt then
        FastPack.worldStartedAt = now() - FastPack.startedAt
    end
    FastPack.setStageReady("after_world_load")
    FastPack.writeRuntimeReport()
end

function FastPack.onCreatePlayer()
    if not FastPack.playerCreatedAt then
        FastPack.playerCreatedAt = now() - FastPack.startedAt
    end
    FastPack.setStageReady("after_player_create")
    FastPack.writeRuntimeReport()
end

Events.OnMainMenuEnter.Add(FastPack.onMainMenuEnter)
Events.OnGameStart.Add(FastPack.onGameStart)
Events.OnCreatePlayer.Add(FastPack.onCreatePlayer)

print("[FastPack] Core " .. FastPack.VERSION .. " loaded")
