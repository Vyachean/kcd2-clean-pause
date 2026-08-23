-- KCD2 Clean Pause
--
-- This file intentionally contains NO controller remapping yet.
-- Input interception is the unresolved part of the design and must be proven
-- without disturbing KCD2's existing action maps.

CleanPause = CleanPause or {
    state = "running",
    previousScale = nil,
}

local function log(message)
    if System and System.LogAlways then
        System.LogAlways("[Clean Pause] " .. tostring(message))
    end
end

local function readScale()
    if not System or not System.GetCVarValue then
        return nil
    end

    return tonumber(System.GetCVarValue("t_scale"))
end

local function writeScale(value)
    if not System or not System.ExecuteCommand then
        return false
    end

    System.ExecuteCommand("t_scale " .. tostring(value))
    return true
end

local function validRestoreScale(value)
    value = tonumber(value)
    if value == nil or value <= 0.0001 then
        return 1.0
    end
    return value
end

function CleanPause.IsPaused()
    return CleanPause.state == "clean_paused"
end

function CleanPause.Enter()
    if CleanPause.state ~= "running" then
        return false
    end

    local current = readScale()
    if current == nil then
        log("enter refused: unable to read t_scale")
        return false
    end

    -- Do not claim a freeze that belongs to the game or another mod.
    if current <= 0.0001 then
        log("enter refused: t_scale is already zero")
        return false
    end

    CleanPause.previousScale = current

    if not writeScale(0) then
        CleanPause.previousScale = nil
        log("enter failed: unable to set t_scale")
        return false
    end

    CleanPause.state = "clean_paused"
    log("entered; previous t_scale=" .. tostring(current))
    return true
end

function CleanPause.Resume()
    if CleanPause.state ~= "clean_paused" then
        return false
    end

    local restore = validRestoreScale(CleanPause.previousScale)

    if not writeScale(restore) then
        log("resume failed: unable to restore t_scale")
        return false
    end

    CleanPause.state = "running"
    CleanPause.previousScale = nil
    log("resumed; t_scale=" .. tostring(restore))
    return true
end

-- Call this immediately before deliberately invoking KCD2's vanilla pause menu.
-- Clean Pause must give up ownership of t_scale first so custom and vanilla
-- pause mechanisms are not stacked on top of each other.
function CleanPause.PrepareVanillaMenu()
    if CleanPause.state == "clean_paused" then
        if not CleanPause.Resume() then
            return false
        end
    end

    log("ready for vanilla pause-menu handoff")
    return true
end

-- Recovery hook for future lifecycle integration. It is safe to call more than
-- once. Do not call it merely because t_scale is zero unless Clean Pause owns
-- the clean-paused state.
function CleanPause.Cleanup()
    if CleanPause.state == "clean_paused" then
        return CleanPause.Resume()
    end

    CleanPause.previousScale = nil
    CleanPause.state = "running"
    return true
end

-- Development-only console commands. They are intentionally NOT bound to any
-- keyboard or controller input. The final input layer will call these state
-- transitions after the vanilla pause action can be intercepted safely.
if System and System.AddCCommand then
    System.AddCCommand(
        "clean_pause_enter",
        "CleanPause.Enter()",
        "Enter Clean Pause without opening a menu."
    )

    System.AddCCommand(
        "clean_pause_resume",
        "CleanPause.Resume()",
        "Resume from Clean Pause."
    )
end

log("state controller loaded; no controller hook installed")
