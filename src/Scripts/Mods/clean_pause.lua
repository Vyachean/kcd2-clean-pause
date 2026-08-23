-- KCD2 Clean Pause
-- Runtime for the pure-profile implementation.
--
-- The build tool patches KCD2's existing pause action in defaultProfile.xml
-- into a console-command action and replaces __CLEAN_PAUSE_COMMAND__ below
-- with that exact retail action name. This avoids supplemental runtime action
-- maps for Start/Menu and preserves the game's existing pause permissions.

CleanPause = CleanPause or {
    state = "running",
}

local PAUSE_COMMAND = "__CLEAN_PAUSE_COMMAND__"
local RESUME_COMMAND = "clean_pause_resume"
local CONTROLS_MAP = "clean_pause_controls"
local INPUT_FILTER = "clean_pause_only"
local MENU_EVENT_SYSTEM = "MenuEvents"
local DISPLAY_INGAME_MENU = "DisplayIngameMenu"

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

local function enableActionMap(name, enabled)
    if not ActionMapManager or not ActionMapManager.EnableActionMap then
        log("ActionMapManager.EnableActionMap unavailable")
        return false
    end

    local ok, err = pcall(function()
        ActionMapManager.EnableActionMap(name, enabled)
    end)
    if not ok then
        log("action map " .. tostring(name) .. " change failed: " .. tostring(err))
        return false
    end

    return true
end

local function enableActionFilter(name, enabled)
    if not ActionMapManager or not ActionMapManager.EnableActionFilter then
        log("ActionMapManager.EnableActionFilter unavailable")
        return false
    end

    local ok, err = pcall(function()
        ActionMapManager.EnableActionFilter(name, enabled)
    end)
    if not ok then
        log("action filter " .. tostring(name) .. " change failed: " .. tostring(err))
        return false
    end

    return true
end

local function enableCleanInput()
    -- The resume action must exist before the actionPass filter starts blocking
    -- everything except the two Clean Pause commands.
    if not enableActionMap(CONTROLS_MAP, true) then
        return false
    end

    if not enableActionFilter(INPUT_FILTER, true) then
        enableActionMap(CONTROLS_MAP, false)
        return false
    end

    return true
end

local function disableCleanInput()
    -- Remove the restrictive filter first, then the temporary B action map.
    local filterOk = enableActionFilter(INPUT_FILTER, false)
    local mapOk = enableActionMap(CONTROLS_MAP, false)
    return filterOk and mapOk
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

    -- ScriptBind_UIAction returns false when neither the element/event-system
    -- nor the requested function exists. A successful event-system call returns
    -- a Lua table, including when the event has no return arguments.
    if result == false or result == nil then
        log("MenuEvents.DisplayIngameMenu(true) unavailable")
        return false
    end

    return true
end

function CleanPause.IsPaused()
    return CleanPause.state == "clean_paused"
end

function CleanPause.Enter()
    if CleanPause.state ~= "running" then
        return false
    end

    -- The retail pause action is only active in contexts where KCD2 allows
    -- pausing. The player guard additionally prevents front-end ownership.
    if player == nil then
        log("pause ignored outside active gameplay")
        return false
    end

    if not pauseGame(true) then
        return false
    end

    if not enableCleanInput() then
        pauseGame(false)
        log("clean input isolation failed; pause rolled back")
        return false
    end

    CleanPause.state = "clean_paused"
    log("entered clean pause")
    return true
end

function CleanPause.Resume()
    if CleanPause.state ~= "clean_paused" then
        return false
    end

    if not disableCleanInput() then
        -- Best effort: re-establish isolation before leaving the game paused.
        enableCleanInput()
        log("resume aborted because clean input could not be released")
        return false
    end

    if not pauseGame(false) then
        enableCleanInput()
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

    -- Keep the game paused while handing ownership to the real menu. Our
    -- Game.PauseGame(true) is non-forced; the vanilla menu upgrades it to its
    -- normal forced pause and owns the eventual resume lifecycle.
    if not disableCleanInput() then
        enableCleanInput()
        log("vanilla menu handoff aborted because clean input could not be released")
        return false
    end

    if not callVanillaMenu() then
        enableCleanInput()
        log("vanilla menu handoff failed; clean pause retained")
        return false
    end

    CleanPause.state = "running"
    log("handed pause ownership to vanilla menu")
    return true
end

function CleanPause.OnPauseAction()
    if CleanPause.state == "clean_paused" then
        return CleanPause.OpenVanillaMenu()
    end

    return CleanPause.Enter()
end

function CleanPause.Cleanup()
    if CleanPause.state == "clean_paused" then
        disableCleanInput()
        pauseGame(false)
    else
        -- Ensure stale state from a script reload cannot leave our additions on.
        disableCleanInput()
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

-- The generated profile invokes these names directly through consoleCmd="1".
addCommand(PAUSE_COMMAND, "CleanPause.OnPauseAction()", "Clean Pause: pause or open the vanilla pause menu.")
addCommand(RESUME_COMMAND, "CleanPause.Resume()", "Clean Pause: resume gameplay.")

-- The custom map/filter are loaded as part of the retail profile, but must never
-- own input outside Clean Pause.
disableCleanInput()

log("pure-profile runtime loaded; pause command=" .. tostring(PAUSE_COMMAND))
