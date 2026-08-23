-- KCD2 Clean Pause
-- Deterministic action-filter prototype.
--
-- Runtime UX:
--   Menu / Start -> Clean Pause (no menu overlay)
--   B            -> resume from Clean Pause
--   Menu / Start -> vanilla KCD2 pause menu when already clean-paused
--
-- Safety invariants:
--   * never calls ActionMapManager.InitActionMaps()
--   * never replaces defaultProfile.xml or controller layouts
--   * reads the effective vanilla defaultProfile.xml version before loading
--     the supplemental action map
--   * unsupported/unknown profile versions fail closed to vanilla controls

CleanPause = CleanPause or {
    state = "running",
    initialized = false,
    profileVersion = nil,
}

local VANILLA_PROFILE = "Libs/Config/defaultProfile.xml"
local SUPPORTED_PROFILE_VERSION = 22
local CUSTOM_PROFILE = "Libs/Config/cleanPauseProfile_v22.xml"

local MAP_CONTROLS = "clean_pause_controls"
local FILTER_BLOCK_VANILLA = "clean_pause_block_vanilla_pause"
local FILTER_CLEAN_ONLY = "clean_pause_only"

local MENU_EVENT_SYSTEM = "MenuEvents"
local DISPLAY_INGAME_MENU = "DisplayIngameMenu"

local function log(message)
    if System and System.LogAlways then
        System.LogAlways("[Clean Pause] " .. tostring(message))
    end
end

local function hasRequiredApis()
    return System
        and type(System.LoadTextFile) == "function"
        and type(System.AddCCommand) == "function"
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

    -- Match the first normal XML element carrying an integer version. This
    -- deliberately does not match the <?xml version=\"1.0\"?> declaration.
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

    -- Event-system calls return a Lua table. ScriptBind_UIAction returns false
    -- when the event system/event cannot be resolved.
    if result == false or result == nil then
        log("MenuEvents.DisplayIngameMenu unavailable")
        return false
    end

    return true
end

function CleanPause.IsPaused()
    return CleanPause.state == "clean_paused"
end

function CleanPause.Enter()
    if not CleanPause.initialized or CleanPause.state ~= "running" then
        return false
    end

    -- Do not let the custom Start action affect the front-end/main menu.
    if player == nil then
        return false
    end

    -- Isolate input before freezing. The current Start event has already been
    -- accepted, so enabling the pass filter here cannot retroactively dispatch
    -- another vanilla action from this physical press.
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

    -- The B event is already in the accepted-event list, so removing the pass
    -- filter here does not cause the same physical press to trigger gameplay.
    setFilter(FILTER_CLEAN_ONLY, false)

    if not pauseGame(false) then
        setFilter(FILTER_CLEAN_ONLY, true)
        log("resume failed; clean pause retained")
        return false
    end

    CleanPause.state = "running"
    log("resumed from native clean pause")
    return true
end

function CleanPause.OpenVanillaMenu()
    if not CleanPause.initialized or CleanPause.state ~= "clean_paused" then
        return false
    end

    -- Keep FILTER_BLOCK_VANILLA enabled. We are not forwarding the current
    -- physical Start event; we invoke KCD2's real MenuEvents subsystem directly.
    -- The vanilla menu will install its own only_ui filter for navigation/B.
    setFilter(FILTER_CLEAN_ONLY, false)

    if not pauseGame(false) then
        setFilter(FILTER_CLEAN_ONLY, true)
        return false
    end

    if not callVanillaMenu(true) then
        -- Roll back atomically to Clean Pause if the menu bridge is absent.
        pauseGame(true)
        setFilter(FILTER_CLEAN_ONLY, true)
        log("vanilla menu handoff failed; clean pause restored")
        return false
    end

    CleanPause.state = "running"
    log("handed pause ownership to vanilla menu")
    return true
end

function CleanPause.StartPressed()
    if CleanPause.state == "clean_paused" then
        return CleanPause.OpenVanillaMenu()
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
    log("disabled; vanilla pause action restored")
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

    -- Confirm our packaged XML can be read before asking the C++ loader to open
    -- it. The script binding does not return LoadFromXML success/failure.
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

    -- Prove both custom filters exist before blocking the vanilla pause action.
    setFilter(FILTER_CLEAN_ONLY, true)
    local cleanOnlyExists = filterEnabled(FILTER_CLEAN_ONLY)
    setFilter(FILTER_CLEAN_ONLY, false)

    if not cleanOnlyExists then
        pcall(function()
            ActionMapManager.EnableActionMap(MAP_CONTROLS, false)
        end)
        log("clean-pause pass filter not loaded; vanilla controls unchanged")
        return false
    end

    if not setFilter(FILTER_BLOCK_VANILLA, true) or not filterEnabled(FILTER_BLOCK_VANILLA) then
        setFilter(FILTER_BLOCK_VANILLA, false)
        pcall(function()
            ActionMapManager.EnableActionMap(MAP_CONTROLS, false)
        end)
        log("vanilla-pause filter not loaded; vanilla controls unchanged")
        return false
    end

    CleanPause.initialized = true
    log(
        "initialized safely; profile version=" .. tostring(version)
        .. "; Start=clean pause, B=resume, Start again=vanilla menu"
    )
    return true
end

-- Console-command action IDs in cleanPauseProfile_v22.xml resolve to these
-- commands. They intentionally exist before the action map is initialized.
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
        "clean_pause_disable",
        "CleanPause.Disable()",
        "Disable Clean Pause input interception for this session."
    )
end

CleanPause.Initialize()
