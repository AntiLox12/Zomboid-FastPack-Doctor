require "ISUI/ISPanel"
require "ISUI/ISButton"
require "ISUI/ISRichTextPanel"
require "ISUI/ISPauseModListUI"

FastPackReportPanel = ISPanel:derive("FastPackReportPanel")

local FONT_SMALL = getTextManager():getFontHeight(UIFont.Small)
local BUTTON_HEIGHT = FONT_SMALL + 10

local function formatDuration(milliseconds)
    local seconds = (tonumber(milliseconds) or 0) / 1000
    if seconds < 60 then
        return string.format("%.2fs", seconds)
    end
    return string.format("%dm %.1fs", math.floor(seconds / 60), seconds % 60)
end

local function buildReportText(statusMessage, statusGood)
    local lines = {}
    table.insert(lines, " <H1> <CENTRE> " .. getText("UI_FastPack_Title"))
    table.insert(lines, " <LINE> <TEXT> <LEFT> " .. getText("UI_FastPack_RuntimeScope"))
    table.insert(lines, " <LINE> <TEXT> <LEFT> <RGB:0.55,0.8,1> "
        .. getText("UI_FastPack_CompanionHint"))
    if statusMessage then
        local color = statusGood and "<GREEN>" or "<RED>"
        table.insert(lines, " <LINE> <TEXT> <LEFT> " .. color .. " " .. statusMessage)
    end
    table.insert(lines, " <LINE> <LINE> <TEXT> <LEFT> <RGB:0.65,0.85,1> " .. getText(
        "UI_FastPack_Summary",
        FastPack.getPendingCount(),
        #FastPack.completed,
        #FastPack.failed,
        #FastPack.warnings
    ))

    if FastPack.menuReachedAt then
        table.insert(lines, " <LINE> <TEXT> <LEFT> " .. getText(
            "UI_FastPack_MenuReached",
            formatDuration(FastPack.menuReachedAt)
        ))
    end
    if FastPack.worldStartedAt then
        table.insert(lines, " <LINE> <TEXT> <LEFT> " .. getText(
            "UI_FastPack_WorldReached",
            formatDuration(FastPack.worldStartedAt)
        ))
    end
    if FastPack.playerCreatedAt then
        table.insert(lines, " <LINE> <TEXT> <LEFT> " .. getText(
            "UI_FastPack_PlayerReached",
            formatDuration(FastPack.playerCreatedAt)
        ))
    end

    table.insert(lines, " <LINE> <LINE> <H2> <LEFT> " .. getText("UI_FastPack_Callbacks"))
    local rows = FastPack.getProfileRows()
    if #rows == 0 then
        table.insert(lines, " <LINE> <TEXT> <LEFT> " .. getText("UI_FastPack_NoCallbacks"))
    else
        for index = 1, math.min(#rows, 30) do
            local row = rows[index]
            table.insert(lines, " <LINE> <TEXT> <LEFT> <RGB:1,0.8,0.35> " .. row.key
                .. " <RGB:1,1,1> " .. tostring(row.calls) .. " calls | "
                .. tostring(row.totalMs) .. "ms total | "
                .. tostring(row.maxMs) .. "ms max")
        end
    end

    table.insert(lines, " <LINE> <LINE> <H2> <LEFT> " .. getText("UI_FastPack_CompletedTasks"))
    if #FastPack.completed == 0 then
        table.insert(lines, " <LINE> <TEXT> <LEFT> " .. getText("UI_FastPack_NoTasks"))
    else
        for index = 1, math.min(#FastPack.completed, 30) do
            local row = FastPack.completed[index]
            table.insert(lines, " <LINE> <TEXT> <LEFT> <RGB:0.55,0.9,0.65> "
                .. row.owner .. ":" .. row.name
                .. " <RGB:1,1,1> " .. tostring(row.totalMs) .. "ms | "
                .. tostring(row.runs) .. " steps")
        end
    end
    if #FastPack.failed > 0 then
        table.insert(lines, " <LINE> <LINE> <H2> <LEFT> " .. getText("UI_FastPack_FailedTasks"))
        for index = 1, math.min(#FastPack.failed, 30) do
            local row = FastPack.failed[index]
            table.insert(lines, " <LINE> <TEXT> <LEFT> <RED> "
                .. row.owner .. ":" .. row.name
                .. " <RGB:1,1,1> " .. tostring(row.error))
        end
    end
    return table.concat(lines)
end

local function openCompanionUrl()
    local opened, errorMessage = pcall(function()
        if type(isSteamOverlayEnabled) == "function"
                and isSteamOverlayEnabled()
                and type(activateSteamOverlayToWebPage) == "function" then
            activateSteamOverlayToWebPage(FastPack.RELEASES_URL)
        elseif type(openUrl) == "function" then
            openUrl(FastPack.RELEASES_URL)
        else
            error("No URL opener is available")
        end
    end)
    if not opened then
        print("[FastPack] Could not open Companion URL: " .. tostring(errorMessage))
    end
    return opened
end

function FastPackReportPanel:initialise()
    ISPanel.initialise(self)

    self.report = ISRichTextPanel:new(12, 12, self.width - 24, self.height - BUTTON_HEIGHT - 36)
    self.report:initialise()
    self.report.background = false
    self.report.autosetheight = false
    self.report.clip = true
    self.report.marginLeft = 8
    self.report.marginRight = 16
    self.report.marginTop = 4
    self.report.marginBottom = 8
    self.report:addScrollBars()
    self:addChild(self.report)

    self.refreshButton = ISButton:new(
        12,
        self.height - BUTTON_HEIGHT - 12,
        130,
        BUTTON_HEIGHT,
        getText("UI_FastPack_Refresh"),
        self,
        FastPackReportPanel.onButton
    )
    self.refreshButton.internal = "REFRESH"
    self.refreshButton:initialise()
    self:addChild(self.refreshButton)

    self.writeButton = ISButton:new(
        self.refreshButton:getRight() + 8,
        self.refreshButton:getY(),
        180,
        BUTTON_HEIGHT,
        getText("UI_FastPack_WriteReport"),
        self,
        FastPackReportPanel.onButton
    )
    self.writeButton.internal = "WRITE"
    self.writeButton:initialise()
    self:addChild(self.writeButton)

    self.githubButton = ISButton:new(
        self.writeButton:getRight() + 8,
        self.refreshButton:getY(),
        190,
        BUTTON_HEIGHT,
        getText("UI_FastPack_OpenGitHub"),
        self,
        FastPackReportPanel.onButton
    )
    self.githubButton.internal = "GITHUB"
    self.githubButton:initialise()
    self:addChild(self.githubButton)

    self.closeButton = ISButton:new(
        self.width - 142,
        self.refreshButton:getY(),
        130,
        BUTTON_HEIGHT,
        getText("UI_Close"),
        self,
        FastPackReportPanel.onButton
    )
    self.closeButton.internal = "CLOSE"
    self.closeButton:initialise()
    self:addChild(self.closeButton)
    self:refresh()
end

function FastPackReportPanel:refresh()
    self.report.text = buildReportText(self.statusMessage, self.statusGood)
    self.report:paginate()
end

function FastPackReportPanel:onButton(button)
    if button.internal == "REFRESH" then
        self.statusMessage = getText("UI_FastPack_StatusRefreshed")
        self.statusGood = true
        self:refresh()
    elseif button.internal == "WRITE" then
        local written = FastPack.writeRuntimeReport()
        self.statusGood = written
        self.statusMessage = written
            and getText("UI_FastPack_StatusWritten", FastPack.REPORT_FILE)
            or getText("UI_FastPack_StatusWriteFailed")
        self:refresh()
    elseif button.internal == "GITHUB" then
        self.statusGood = openCompanionUrl()
        self.statusMessage = self.statusGood
            and getText("UI_FastPack_StatusBrowserOpened")
            or getText("UI_FastPack_StatusBrowserFailed")
        self:refresh()
    elseif button.internal == "CLOSE" then
        self:close()
    end
end

function FastPackReportPanel:onKeyRelease(key)
    if key == Keyboard.KEY_ESCAPE then
        self:close()
    end
end

function FastPackReportPanel:close()
    self:setCapture(false)
    self:removeFromUIManager()
    if FastPack.reportPanel == self then
        FastPack.reportPanel = nil
    end
end

function FastPackReportPanel:new(x, y, width, height)
    local object = ISPanel.new(self, x, y, width, height)
    object.backgroundColor = { r = 0.04, g = 0.05, b = 0.06, a = 0.97 }
    object.borderColor = { r = 0.9, g = 0.65, b = 0.25, a = 0.9 }
    object.moveWithMouse = true
    return object
end

function FastPack.openReport()
    if FastPack.reportPanel then
        FastPack.reportPanel:close()
    end
    local screenWidth = getCore():getScreenWidth()
    local screenHeight = getCore():getScreenHeight()
    local width = math.min(860, screenWidth - 60)
    local height = math.min(680, screenHeight - 60)
    local panel = FastPackReportPanel:new(
        math.floor((screenWidth - width) / 2),
        math.floor((screenHeight - height) / 2),
        width,
        height
    )
    panel:initialise()
    panel:addToUIManager()
    panel:setCapture(true)
    panel:setAlwaysOnTop(true)
    FastPack.reportPanel = panel
end

function FastPack.onPauseReportButton()
    FastPack.openReport()
end

function FastPack.installPauseModListPatch()
    if FastPack.pausePatchInstalled or not ISPauseModListUI then
        return
    end

    local originalInitialise = ISPauseModListUI.initialise
    function ISPauseModListUI:initialise()
        originalInitialise(self)
        if self.fastPackButton then
            return
        end
        local button = ISButton:new(
            self.width - 190,
            10,
            180,
            BUTTON_HEIGHT,
            getText("UI_FastPack_Open"),
            self,
            FastPack.onPauseReportButton
        )
        button:initialise()
        self:addChild(button)
        self.fastPackButton = button
        self.chatText:setY(BUTTON_HEIGHT + 18)
        self.chatText:setHeight(self.height - BUTTON_HEIGHT - 18)
    end

    FastPack.pausePatchInstalled = true
    print("[FastPack] Pause mod-list report button installed")
end

FastPack.installPauseModListPatch()
Events.OnGameStart.Add(FastPack.installPauseModListPatch)
