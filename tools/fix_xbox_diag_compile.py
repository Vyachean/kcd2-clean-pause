#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "native/src/clean_pause_native.cpp"
text = path.read_text(encoding="utf-8")

old = '''    case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:
        // Preserve the runtime-tested Xbox bootstrap boundary: the exact Xbox PE
        // fingerprint has already selected this adapter, and the legacy scanner
        // validates the complete SSystemGlobalEnvironment interface shape. Do not
        // call engine virtuals such as IGame::GetName()/IGame[16] from this worker
        // thread. The optional framework identity is verified later, immediately
        // before its PauseGame observer is installed.
        if (!LegacyFindRuntimeEnvironment_Xbox156Only(whGame, result)) {
            failureReason = "xbox-runtime-not-ready";
            return false;
        }
        observedCandidate = result;
        const auto* moduleBase = reinterpret_cast<const std::uint8_t*>(whGame);
        const auto envRva = static_cast<unsigned long long>(result.base - moduleBase);
        Log("Xbox legacy runtime environment discovered; WHGame=%p env=%p envRva=0x%llx mainThread=%lu",
            whGame,
            result.base,
            envRva,
            static_cast<unsigned long>(result.mainThreadId));
        return true;

'''
new = '''    case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan: {
        // Preserve the runtime-tested Xbox bootstrap boundary: the exact Xbox PE
        // fingerprint has already selected this adapter, and the legacy scanner
        // validates the complete SSystemGlobalEnvironment interface shape. Do not
        // call engine virtuals such as IGame::GetName()/IGame[16] from this worker
        // thread. The optional framework identity is verified later, immediately
        // before its PauseGame observer is installed.
        if (!LegacyFindRuntimeEnvironment_Xbox156Only(whGame, result)) {
            failureReason = "xbox-runtime-not-ready";
            return false;
        }
        observedCandidate = result;
        const auto* moduleBase = reinterpret_cast<const std::uint8_t*>(whGame);
        const auto* environmentBase = reinterpret_cast<const std::uint8_t*>(result.base);
        const auto envRva = static_cast<unsigned long long>(environmentBase - moduleBase);
        Log("Xbox legacy runtime environment discovered; WHGame=%p env=%p envRva=0x%llx mainThread=%lu",
            whGame,
            result.base,
            envRva,
            static_cast<unsigned long>(result.mainThreadId));
        return true;
    }

'''
if old not in text:
    raise RuntimeError("Xbox diagnostic environment block not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Xbox diagnostic compile fix applied")
