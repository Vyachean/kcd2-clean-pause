-- KCD2 Clean Pause
-- Official-mod runtime for the exact-profile build.
--
-- The build tool patches the target installation's existing open_menu and
-- open_pause_menu actions into console-command actions while preserving their
-- original action ids and physical bindings. KCD2 therefore still decides when
-- those actions are valid through its normal action maps and filters.

CleanPause = CleanPause or {
    state = "running",
}

local GAMEPLAY_COMMAND = "__CLEAN_PAUSE_GAMEPLAY_COMMAND__"
local PAUSE_COMMAND = "__CLEAN_PAUSE_PAUSE_COMMAND__"
local RESUME_COMMAND = "clean_pause_resume"
local MENU_COMMAND = "clean_pause_open_menu"
local CONTROLS_MAP = "clean_pause_controls"
local MENU_EVENT_SYSTEM = "MenuEvents"
local DISPLAY_INGAME_MENU = "DisplayIngameMenu"
local FILTER_ONLY_UI = "only_ui"

local function log(message)
    if System and System.LogAlways then
        System.LogAlways("[Clean Pause] " .. tostring(message))
    end
end

local function pauseGame(paused)
    if not Game or not Game.PauseGame then
        log("Game.PauseGame unavailable")
        return false
    end

    local ok, err = pcall(function()
        Game.PauseGame(paused)
    end)
    if not ok then
        log("Game.PauseGame(" .. tostring(paused) .. ") failed: " .. tostring(err))
        return false
    end

    return true
end

local function setControlsEnabled(enabled)
    if not ActionMapManager or not ActionMapManager.EnableActionMap then
        log("ActionMapManager.EnableActionMap unavailable")
        return false
    end

    local ok, err = pcall(function()
        ActionMapManager.EnableActionMap(CONTROLS_MAP, enabled)
    end)
    if not ok then
        log("controls map change failed: " .. tostring(err))
        return false
    end

    return true
end

local function isVanillaUiOnly()
    if not ActionMapManager or not ActionMapManager.IsFilterEnabled then
        return false
    end

    local ok, result = pcall(function()
        return ActionMapManager.IsFilterEnabled(FILTER_ONLY_UI)
    end)
    return ok and result == true
end

local function callVanillaMenu()
    if not UIAction or not UIAction.CallFunction then
        log("UIAction.CallFunction unavailable")
        return false
    end

    local ok, result = pcall(function()
        return UIAction.CallFunction(
            MENU_EVENT_SYSTEM,
            -1,
            DISPLAY_INGAME_MENU,
            true
        )
    end)
    if not ok then
        log("MenuEvents.DisplayIngameMenu threw: " .. tostring(result))
        return false
    end

    if result == false or result == nil then
        log("MenuEvents.DisplayIngameMenu(true) unavailable")
        return false
    end

    return true
end

function CleanPause.IsPaused()
    return CleanPause.state == "clean_paused"
end

function CleanPause.Enter(sourceAction)
    if CleanPause.state ~= "running" then
        return false
    end

    if player == nil then
        log("pause ignored outside active gameplay")
        return false
    end
    if isVanillaUiOnly() then
        log("pause ignored while vanilla only_ui filter is active")
        return false
    end

    if not setControlsEnabled(true) then
        return false
    end

    if not pauseGame(true) then
        setControlsEnabled(false)
        return false
    end

    CleanPause.state = "clean_paused"
    log("entered clean pause from " .. tostring(sourceAction))
    return true
end

function CleanPause.Resume()
    if CleanPause.state ~= "clean_paused" then
        return false
    end

    if not setControlsEnabled(false) then
        log("resume aborted because controls map could not be disabled")
        return false
    end

    if not pauseGame(false) then
        setControlsEnabled(true)
        log("resume failed; clean pause retained")
        return false
    end

    CleanPause.state = "running"
    log("resumed")
    return true
end

function CleanPause.OpenVanillaMenu()
    if CleanPause.state ~= "clean_paused" then
        return false
    end

    if not setControlsEnabled(false) then
        log("vanilla-menu handoff aborted because controls map could not be disabled")
        return false
    end

    if not callVanillaMenu() then
        setControlsEnabled(true)
        log("vanilla-menu handoff failed; clean pause retained")
        return false
    end

    CleanPause.state = "running"
    log("handed pause ownership to vanilla menu")
    return true
end

function CleanPause.OnPauseAction(sourceAction)
    if CleanPause.state == "clean_paused" then
        return CleanPause.OpenVanillaMenu()
    end

    return CleanPause.Enter(sourceAction)
end

function CleanPause.Cleanup()
    setControlsEnabled(false)
    if CleanPause.state == "clean_paused" then
        pauseGame(false)
    end
    CleanPause.state = "running"
    return true
end

local function addCommand(name, luaCode, description)
    if not System or not System.AddCCommand then
        log("System.AddCCommand unavailable; cannot register " .. tostring(name))
        return false
    end

    local ok, err = pcall(function()
        System.AddCCommand(name, luaCode, description)
    end)
    if not ok then
        log("failed to register command " .. tostring(name) .. ": " .. tostring(err))
        return false
    end

    return true
end

addCommand(
    GAMEPLAY_COMMAND,
    'CleanPause.OnPauseAction("' .. GAMEPLAY_COMMAND .. '")',
    "Clean Pause: route KCD2 gameplay pause action."
)
addCommand(
    PAUSE_COMMAND,
    'CleanPause.OnPauseAction("' .. PAUSE_COMMAND .. '")',
    "Clean Pause: route KCD2 contextual pause action."
)
addCommand(MENU_COMMAND, "CleanPause.OpenVanillaMenu()", "Clean Pause: open vanilla pause menu.")
addCommand(RESUME_COMMAND, "CleanPause.Resume()", "Clean Pause: resume gameplay.")

setControlsEnabled(false)

log(
    "official runtime loaded; routed actions="
        .. tostring(GAMEPLAY_COMMAND)
        .. ","
        .. tostring(PAUSE_COMMAND)
)
