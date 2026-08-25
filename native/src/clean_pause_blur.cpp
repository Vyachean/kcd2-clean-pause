#include "clean_pause_blur.h"
#include "kcd2_abi.h"

#include <atomic>
#include <cstring>
#include <windows.h>

namespace clean_pause::blur {
namespace {

void* g_scriptSystem{};
DWORD g_mainThreadId{};
std::atomic_bool g_suppressed{false};

bool ExecuteLua(const char* code, const char* source)
{
    if (!g_scriptSystem || !code)
        return false;
    if (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId)
        return false;

    const auto execute = kcd2::VFunc<kcd2::ExecuteBufferFn>(
        g_scriptSystem, kcd2::kScriptExecuteBufferSlot);
    if (!execute)
        return false;

    bool ok{};
    __try {
        ok = execute(
            g_scriptSystem,
            code,
            std::strlen(code),
            source ? source : "@kcd2_clean_pause/blur",
            nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }
    return ok;
}

constexpr const char* kDisableScript = R"lua(
if not System or not System.GetCVarValue or not System.SetCVar then
    error("Clean Pause CVar API unavailable")
end
if __kcd2_clean_pause_blur_active then
    return
end
__kcd2_clean_pause_prev_near_dof = System.GetCVarValue("wh_cl_NearDof")
__kcd2_clean_pause_prev_depth_of_field = System.GetCVarValue("r_DepthOfField")
if __kcd2_clean_pause_prev_near_dof == nil or __kcd2_clean_pause_prev_depth_of_field == nil then
    error("Clean Pause DoF CVar unavailable")
end
System.SetCVar("wh_cl_NearDof", 0)
System.SetCVar("r_DepthOfField", 0)
__kcd2_clean_pause_blur_active = true
)lua";

constexpr const char* kRestoreScript = R"lua(
if not System or not System.SetCVar then
    error("Clean Pause CVar API unavailable")
end
if __kcd2_clean_pause_prev_near_dof ~= nil then
    System.SetCVar("wh_cl_NearDof", __kcd2_clean_pause_prev_near_dof)
end
if __kcd2_clean_pause_prev_depth_of_field ~= nil then
    System.SetCVar("r_DepthOfField", __kcd2_clean_pause_prev_depth_of_field)
end
__kcd2_clean_pause_prev_near_dof = nil
__kcd2_clean_pause_prev_depth_of_field = nil
__kcd2_clean_pause_blur_active = nil
)lua";

} // namespace

void Initialize(void* scriptSystem, std::uint32_t mainThreadId)
{
    g_scriptSystem = scriptSystem;
    g_mainThreadId = static_cast<DWORD>(mainThreadId);
    g_suppressed.store(false, std::memory_order_release);
}

bool Disable()
{
    if (g_suppressed.load(std::memory_order_acquire))
        return true;

    if (!ExecuteLua(kDisableScript, "@kcd2_clean_pause/disable_blur")) {
        // The first SetCVar could have succeeded before a later Lua error. Restore
        // best-effort before refusing Clean Pause so graphics never remain modified.
        ExecuteLua(kRestoreScript, "@kcd2_clean_pause/disable_blur_rollback");
        return false;
    }

    g_suppressed.store(true, std::memory_order_release);
    return true;
}

bool Restore()
{
    if (!g_suppressed.load(std::memory_order_acquire))
        return true;

    if (!ExecuteLua(kRestoreScript, "@kcd2_clean_pause/restore_blur"))
        return false;

    g_suppressed.store(false, std::memory_order_release);
    return true;
}

bool IsSuppressed()
{
    return g_suppressed.load(std::memory_order_acquire);
}

} // namespace clean_pause::blur
