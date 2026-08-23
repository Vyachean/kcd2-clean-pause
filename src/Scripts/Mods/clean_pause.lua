-- KCD2 Clean Pause
-- Experimental pure-Lua prototype.
--
-- Goal:
--   Menu / Start from gameplay -> native game pause with NO pause-menu UI.
--   B / ui_back while clean-paused -> resume.
--   Menu / Start while clean-paused -> hand off to KCD2's vanilla pause menu.
--
-- Safety:
--   This mod never calls ActionMapManager.InitActionMaps(), never replaces
--   controller mappings, and never installs a parallel controller binding.
--   If the vanilla MenuEvents bridge is unavailable, the normal pause menu is
--   left alone rather than trying to take ownership of the pause state.

CleanPause = CleanPause or {
    state = "running",
    hookInstalled = false,
    originalPlayerOnAction = nil,
}

local MENU_EVENT_SYSTEM = "MenuEvents"
local DISPLAY_INGAME_MENU = "DisplayIngameMenu"
local FILTER_ONLY_UI = "only_ui"

local function log(message)
    if System and System.LogAlways then
        System.LogAlways("[Clean Pause] " .. tostring(message))
    end
end

local function isPress(activation)
    -- KCD2 player.lua uses the string form; numeric 1 is accepted defensively
    -- for CryEngine-style eAAM_OnPress callers.
    return activation == "press" or activation == 1
end

local function callMenu(display)
    if not UIAction or not UIAction.CallFunction then
        log("MenuEvents bridge unavailable: UIAction.CallFunction missing")
        return false
    end

    local ok, result = pcall(function()
        return UIAction.CallFunction(
            MENU_EVENT_SYSTEM,
            0,
            DISPLAY_INGAME_MENU,
            display
        )
    end)

    if not ok then
        log("MenuEvents bridge threw: " .. tostring(result))
        return false
    end

    -- ScriptBind_UIAction returns false when neither the UI element nor the
    -- requested UI-to-system event exists. A successful event-system call
    -- returns a Lua table (possibly empty), which is truthy.
    if result == false or result == nil then
        log("MenuEvents.DisplayIngameMenu(" .. tostring(display) .. ") unavailable")
        return false
    end

    return true
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

local function setOnlyUi(enabled)
    if not ActionMapManager or not ActionMapManager.EnableActionFilter then
        log("only_ui filter API unavailable; continuing without filter change")
        return false
    end

    local ok, err = pcall(function()
        ActionMapManager.EnableActionFilter(FILTER_ONLY_UI, enabled)
    end)

    if not ok then
        log("only_ui filter change failed: " .. tostring(err))
        return false
    end

    return true
end

function CleanPause.IsPaused()
    return CleanPause.state == "clean_paused"
end

-- Enter clean pause after KCD2 has emitted ui_start_pause.
--
-- The critical trick is to use KCD2/CryEngine's own MenuEvents bridge to hide
-- the vanilla ingame menu synchronously, then immediately acquire native game
-- pause without emitting the menu's OnStartIngameMenu UI event.
--
-- If MenuEvents is not present on the retail build, this function fails closed:
-- the vanilla pause menu remains in control.
function CleanPause.EnterFromStartAction()
    if CleanPause.state ~= "running" then
        return false
    end

    if player == nil then
        -- Do not touch front-end/main-menu input.
        return false
    end

    if not callMenu(false) then
        log("clean-pause entry aborted; vanilla pause remains authoritative")
        return false
    end

    if not pauseGame(true) then
        -- Menu was closed but native pause could not be acquired. Restore the
        -- ordinary menu immediately rather than leaving a surprising state.
        callMenu(true)
        log("clean-pause entry rolled back to vanilla menu")
        return false
    end

    -- Match the input isolation normally applied by the vanilla ingame menu.
    -- This does not alter bindings; it only enables the game's existing UI-only
    -- action filter. ui_back and ui_start_pause are expected to remain usable.
    setOnlyUi(true)

    CleanPause.state = "clean_paused"
    log("entered native clean pause")
    return true
end

function CleanPause.Resume()
    if CleanPause.state ~= "clean_paused" then
        return false
    end

    -- Remove UI-only isolation before unpausing so normal gameplay input is
    -- available as soon as the simulation resumes.
    setOnlyUi(false)

    if not pauseGame(false) then
        -- Best effort: put the filter back if we failed to relinquish pause.
        setOnlyUi(true)
        log("resume failed; clean pause retained")
        return false
    end

    CleanPause.state = "running"
    log("resumed from native clean pause")
    return true
end

function CleanPause.OpenVanillaMenu()
    if CleanPause.state ~= "clean_paused" then
        return false
    end

    -- The game is already natively paused. Ask the real MenuEvents subsystem to
    -- display its own menu and take ownership of input filtering/pause lifecycle.
    -- DisplayIngameMenu(true) is idempotent if the vanilla Start handler already
    -- opened it earlier in the same input cycle.
    if not callMenu(true) then
        log("vanilla menu handoff failed; clean pause retained")
        return false
    end

    CleanPause.state = "running"
    log("handed pause ownership to vanilla menu")
    return true
end

function CleanPause.OnPlayerAction(action, activation, value)
    if not isPress(activation) then
        return
    end

    if action == "ui_start_pause" then
        log("observed ui_start_pause; state=" .. tostring(CleanPause.state))

        if CleanPause.state == "clean_paused" then
            CleanPause.OpenVanillaMenu()
        else
            CleanPause.EnterFromStartAction()
        end

        return
    end

    if action == "ui_back" and CleanPause.state == "clean_paused" then
        log("observed ui_back while clean-paused")
        CleanPause.Resume()
    end
end

function CleanPause.InstallPlayerHook()
    if CleanPause.hookInstalled then
        return true
    end

    if not Player or type(Player.OnAction) ~= "function" then
        log("Player.OnAction unavailable; no input hook installed")
        return false
    end

    CleanPause.originalPlayerOnAction = Player.OnAction

    Player.OnAction = function(self, action, activation, value)
        -- Preserve the entire vanilla Player.OnAction path. Clean Pause is an
        -- observer layered around it, not a replacement for game rules/player
        -- action handling.
        local result = CleanPause.originalPlayerOnAction(self, action, activation, value)

        CleanPause.OnPlayerAction(action, activation, value)
        return result
    end

    CleanPause.hookInstalled = true
    log("Player.OnAction hook installed")
    return true
end

-- Recovery for development/testing. Never changes controller mappings.
function CleanPause.Cleanup()
    if CleanPause.state == "clean_paused" then
        setOnlyUi(false)
        pauseGame(false)
    end

    CleanPause.state = "running"
    return true
end

-- Development commands make it possible to isolate pause-state problems from
-- Menu/Start routing problems when testing with a keyboard/console available.
if System and System.AddCCommand then
    System.AddCCommand(
        "clean_pause_enter",
        "CleanPause.EnterFromStartAction()",
        "Attempt native Clean Pause using the MenuEvents bridge."
    )

    System.AddCCommand(
        "clean_pause_resume",
        "CleanPause.Resume()",
        "Resume from native Clean Pause."
    )

    System.AddCCommand(
        "clean_pause_menu",
        "CleanPause.OpenVanillaMenu()",
        "Open the vanilla pause menu from Clean Pause."
    )
end

CleanPause.InstallPlayerHook()
log("prototype loaded; no controller mappings modified")
