#pragma once

#include <cstdint>

namespace clean_pause::blur {

void Initialize(void* scriptSystem, std::uint32_t mainThreadId);
bool Disable();
bool Restore();
bool IsSuppressed();

} // namespace clean_pause::blur
