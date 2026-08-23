-- KCD2 Clean Pause
-- Deterministic action-filter prototype with a safe controller-input handshake.
--
-- Development UX:
--   First gameplay Menu / Start after loading a save -> vanilla pause once.
--     This proves that the supplemental clean_pause_start action really fired.
--   After the vanilla menu is closed:
--     Menu / Start -> Clean Pause (no menu overlay)
--     B            -> resume from Clean Pause
--     Menu / Start -> vanilla KCD2 pause menu when already clean-paused
--
-- Safety invariants:
--   * never calls ActionMapManager.InitActionMaps()
--   * never replaces defaultProfile.xml or controller layouts
--   * reads the effective vanilla defaultProfile.xml version before loading
--     the supplemental action map
--   * unsupported/unknown profile versions fail closed to vanilla controls
--   * ui_start_pause is never blocked until the physical Start mapping has
--     successfully invoked clean_pause_start at least once in active gameplay

CleanPause = CleanPause or {
    state = "running",
    initialized = false,
    profileVersion = nil,
    monitorScheduled = false,
    inputHandshakeSeen = false,
    handshakeGraceTicks = 0,
}

local VANILLA_PROFILE = "Libs/Config/defaultProfile.xml"
local SUPPORTED_PROFILE_VERSION = 22
local CUSTOM_PROFILE = "Libs/Config/cleanPauseProfile_v22.xml"

local MAP_CONTROLS = "clean_pause_controls"
local FILTER_BLOCK_VANILLA = "clean_pause_block_vanilla_pause"
local FILTER_CLEAN_ONLY = "clean_pause_only"
local FILTER_ONLY_UI = "only_ui"

local MENU_EVENT_SYSTEM = "MenuEvents"
local DISPLAY_INGAME_MENU = "DisplayIngameMenu"
local MONITOR_INTERVAL_MS = 100
local HANDSHAKE_GRACE_TICKS = 10

local function log(message)
    if System and System.LogAlways then
        System.LogAlways("[Clean Pause] " .. tostring(message))
    end
end

local function hasRequiredApis()
    return System
        and type(System.LoadTextFile) == "function"
        and type(System.AddCCommand) == "function"
        and Script
        and type(Script.SetTimer) == "function"
        and ActionMapManager
        and type(ActionMapManager.LoadFromXML) == "function"
        and type(ActionMapManager.EnableActionMap) == "function"
        and type(ActionMapManager.EnableActionFilter) == "function"
        and type(ActionMapManager.IsFilterEnabled) == "function"
        and Game
        and type(Game.PauseGame) == "function"
        and UIAction
        and type(UIAction.CallFunction) == "function"
end

local function loadText(path)
    local ok, result = pcall(function()
        return System.LoadTextFile(path)
    end)

    if not ok or type(result) ~= "string" or result == "" then
        return nil
    end

    return result
end

local function readProfileVersion()
    local text = loadText(VANILLA_PROFILE)
    if not text then
        log("cannot read " .. VANILLA_PROFILE .. "; input hook not installed")
        return nil
    end

    local value = string.match(
        text,
        "<[%a_][%w_:%-%.]*[^>]-version%s*=%s*[\"'](%d+)[\"']"
    )

    local version = tonumber(value)
    if not version then
        log("cannot determine defaultProfile.xml version; input hook not installed")
        return nil
    end

    return version
end

local function setFilter(name, enabled)
    local ok, err = pcall(function()
        ActionMapManager.EnableActionFilter(name, enabled)
    end)

    if not ok then
        log("filter " .. name .. " change failed: " .. tostring(err))
        return false
    end

    return true
end

local function filterEnabled(name)
    local ok, result = pcall(function()
        return ActionMapManager.IsFilterEnabled(name)
    end)

    return ok and result == true
end

local function pauseGame(paused)
    local ok, err = pcall(function()
        Game.PauseGame(paused)
    end)

    if not ok then
        log("Game.PauseGame(" .. tostring(paused) .. ") failed: " .. tostring(err))
        return false
    end

    return true
end

local function callVanillaMenu(display)
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

    if result == false or result == nil then
        log("MenuEvents.DisplayIngameMenu unavailable")
        return false
    end

    return true
end

local function shouldInterceptVanillaPause()
    if not CleanPause.initialized then
        return false
    end

    if CleanPause.state == "clean_paused" then
        return true
    end

    -- Never take Start away from KCD2 until our own xi_start action has proved
    -- itself by firing once in active gameplay.
    if not CleanPause.inputHandshakeSeen then
        return false
    end

    -- Give the first (deliberately vanilla) Start press time to finish opening
    -- the real pause menu before interception can become eligible.
    if CleanPause.handshakeGraceTicks > 0 then
        return false
    end

    -- Main/front-end menus have no player. KCD2's real pause/menu UI uses the
    -- existing only_ui pass filter; while it is active Start remains vanilla.
    return player ~= nil and not filterEnabled(FILTER_ONLY_UI)
end

function CleanPause.RefreshInterception()
    if not CleanPause.initialized then
        return false
    end

    if CleanPause.state == "clean_paused" and player == nil then
        setFilter(FILTER_CLEAN_ONLY, false)
        pauseGame(false)
        CleanPause.state = "running"
        log("player disappeared; clean pause recovered")
    end

    if CleanPause.handshakeGraceTicks > 0 then
        CleanPause.handshakeGraceTicks = CleanPause.handshakeGraceTicks - 1
    end

    local desired = shouldInterceptVanillaPause()
    local current = filterEnabled(FILTER_BLOCK_VANILLA)

    if desired ~= current then
        if not setFilter(FILTER_BLOCK_VANILLA, desired) then
            return false
        end

        if filterEnabled(FILTER_BLOCK_VANILLA) ~= desired then
            log("vanilla pause interception state could not be verified")
            return false
        end

        log("vanilla pause interception=" .. tostring(desired))
    end

    return true
end

function CleanPause.OnMonitorTimer(userData, timerId)
    CleanPause.monitorScheduled = false

    if not CleanPause.initialized then
        return
    end

    CleanPause.RefreshInterception()
    CleanPause.ScheduleMonitor()
end

function CleanPause.ScheduleMonitor()
    if not CleanPause.initialized or CleanPause.monitorScheduled then
        return false
    end

    local ok, result = pcall(function()
        return Script.SetTimer(
            MONITOR_INTERVAL_MS,
            CleanPause.OnMonitorTimer,
            CleanPause,
            true
        )
    end)

    if not ok or result == nil then
        log("lifecycle monitor could not be scheduled; disabling interception")
        setFilter(FILTER_BLOCK_VANILLA, false)
        CleanPause.initialized = false
        CleanPause.monitorScheduled = false
        return false
    end

    CleanPause.monitorScheduled = true
    return true
end

function CleanPause.IsPaused()
    return CleanPause.state == "clean_paused"
end

function CleanPause.Enter()
    if not CleanPause.initialized or CleanPause.state ~= "running" then
        return false
    end

    if player == nil or not filterEnabled(FILTER_BLOCK_VANILLA) then
        return false
    end

    if not setFilter(FILTER_CLEAN_ONLY, true) or not filterEnabled(FILTER_CLEAN_ONLY) then
        setFilter(FILTER_CLEAN_ONLY, false)
        log("clean-pause input isolation failed; pause not entered")
        return false
    end

    if not pauseGame(true) then
        setFilter(FILTER_CLEAN_ONLY, false)
        return false
    end

    CleanPause.state = "clean_paused"
    log("entered native clean pause")
    return true
end

function CleanPause.Resume()
    if not CleanPause.initialized or CleanPause.state ~= "clean_paused" then
        return false
    end

    setFilter(FILTER_CLEAN_ONLY, false)

    if not pauseGame(false) then
        setFilter(FILTER_CLEAN_ONLY, true)
        log("resume failed; clean pause retained")
        return false
    end

    CleanPause.state = "running"
    CleanPause.RefreshInterception()
    log("resumed from native clean pause")
    return true
end

function CleanPause.OpenVanillaMenu()
    if not CleanPause.initialized or CleanPause.state ~= "clean_paused" then
        return false
    end

    setFilter(FILTER_CLEAN_ONLY, false)
    setFilter(FILTER_BLOCK_VANILLA, false)

    if not pauseGame(false) then
        setFilter(FILTER_BLOCK_VANILLA, true)
        setFilter(FILTER_CLEAN_ONLY, true)
        return false
    end

    if not callVanillaMenu(true) then
        pauseGame(true)
        setFilter(FILTER_BLOCK_VANILLA, true)
        setFilter(FILTER_CLEAN_ONLY, true)
        log("vanilla menu handoff failed; clean pause restored")
        return false
    end

    CleanPause.state = "running"
    CleanPause.handshakeGraceTicks = HANDSHAKE_GRACE_TICKS
    log("handed pause ownership to vanilla menu")
    return true
end

function CleanPause.StartPressed()
    if not CleanPause.initialized then
        return false
    end

    if CleanPause.state == "clean_paused" then
        return CleanPause.OpenVanillaMenu()
    end

    if player == nil then
        return false
    end

    if not CleanPause.inputHandshakeSeen then
        -- Critical development handshake: the custom action has now proved that
        -- LoadFromXML + xi_start + consoleCmd actually works on this retail build.
        -- Keep the vanilla ui_start_pause unfiltered for THIS press, so a broken
        -- prototype can never strand the user without the normal pause menu.
        CleanPause.inputHandshakeSeen = true
        CleanPause.handshakeGraceTicks = HANDSHAKE_GRACE_TICKS
        setFilter(FILTER_BLOCK_VANILLA, false)
        log("controller Start handshake observed; first pause intentionally left vanilla")
        return false
    end

    return CleanPause.Enter()
end

function CleanPause.Disable()
    if CleanPause.state == "clean_paused" then
        setFilter(FILTER_CLEAN_ONLY, false)
        pauseGame(false)
    end

    setFilter(FILTER_CLEAN_ONLY, false)
    setFilter(FILTER_BLOCK_VANILLA, false)

    if ActionMapManager and ActionMapManager.EnableActionMap then
        pcall(function()
            ActionMapManager.EnableActionMap(MAP_CONTROLS, false)
        end)
    end

    CleanPause.state = "running"
    CleanPause.initialized = false
    CleanPause.monitorScheduled = false
    CleanPause.inputHandshakeSeen = false
    CleanPause.handshakeGraceTicks = 0
    log("disabled; vanilla pause action restored")
    return true
end

function CleanPause.Status()
    log(
        "status initialized=" .. tostring(CleanPause.initialized)
        .. " profileVersion=" .. tostring(CleanPause.profileVersion)
        .. " handshake=" .. tostring(CleanPause.inputHandshakeSeen)
        .. " blockVanilla=" .. tostring(filterEnabled(FILTER_BLOCK_VANILLA))
        .. " onlyUi=" .. tostring(filterEnabled(FILTER_ONLY_UI))
        .. " state=" .. tostring(CleanPause.state)
    )
    return true
end

function CleanPause.Initialize()
    if CleanPause.initialized then
        return true
    end

    if not hasRequiredApis() then
        log("required retail Lua APIs unavailable; vanilla controls unchanged")
        return false
    end

    local version = readProfileVersion()
    CleanPause.profileVersion = version

    if version ~= SUPPORTED_PROFILE_VERSION then
        log(
            "unsupported defaultProfile.xml version " .. tostring(version)
            .. " (supported: " .. tostring(SUPPORTED_PROFILE_VERSION)
            .. "); vanilla controls unchanged"
        )
        return false
    end

    local customText = loadText(CUSTOM_PROFILE)
    if not customText then
        log("custom input profile missing; vanilla controls unchanged")
        return false
    end

    if not string.find(customText, "<profile version=\"22\"", 1, true) then
        log("custom input profile version mismatch; vanilla controls unchanged")
        return false
    end

    local ok, err = pcall(function()
        ActionMapManager.LoadFromXML(CUSTOM_PROFILE)
        ActionMapManager.EnableActionMap(MAP_CONTROLS, true)
    end)

    if not ok then
        log("custom input profile load failed: " .. tostring(err))
        return false
    end

    -- Prove the supplemental filters were created, then leave BOTH disabled.
    -- The vanilla pause filter is not allowed to turn on before the real
    -- controller-action handshake in StartPressed().
    setFilter(FILTER_CLEAN_ONLY, true)
    local cleanOnlyExists = filterEnabled(FILTER_CLEAN_ONLY)
    setFilter(FILTER_CLEAN_ONLY, false)

    setFilter(FILTER_BLOCK_VANILLA, true)
    local blockVanillaExists = filterEnabled(FILTER_BLOCK_VANILLA)
    setFilter(FILTER_BLOCK_VANILLA, false)

    if not cleanOnlyExists or not blockVanillaExists then
        pcall(function()
            ActionMapManager.EnableActionMap(MAP_CONTROLS, false)
        end)
        log("supplemental filters not loaded; vanilla controls unchanged")
        return false
    end

    CleanPause.initialized = true
    CleanPause.inputHandshakeSeen = false
    CleanPause.handshakeGraceTicks = 0

    if not CleanPause.ScheduleMonitor() then
        CleanPause.Disable()
        return false
    end

    log(
        "initialized safely; profile version=" .. tostring(version)
        .. "; waiting for first gameplay Start handshake"
    )
    return true
end

if System and System.AddCCommand then
    System.AddCCommand(
        "clean_pause_start",
        "CleanPause.StartPressed()",
        "Clean Pause: Start/Menu action."
    )

    System.AddCCommand(
        "clean_pause_resume",
        "CleanPause.Resume()",
        "Clean Pause: resume action."
    )

    System.AddCCommand(
        "clean_pause_status",
        "CleanPause.Status()",
        "Clean Pause: log current diagnostic state."
    )

    System.AddCCommand(
        "clean_pause_disable",
        "CleanPause.Disable()",
        "Disable Clean Pause input interception for this session."
    )
end

CleanPause.Initialize()
