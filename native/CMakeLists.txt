cmake_minimum_required(VERSION 3.24)
project(kcd2_clean_pause_native LANGUAGES C CXX)

if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "The native prototype currently targets 64-bit Windows/MSVC only.")
endif()

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "KCD2 Clean Pause requires a 64-bit build.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>" CACHE STRING "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)

include(FetchContent)
FetchContent_Declare(
  minhook
  GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
  GIT_TAG v1.3.4
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(minhook)

set(CLEAN_PAUSE_RUNTIME_SOURCES
  src/clean_pause_native.cpp
  src/clean_pause_native.h
  src/clean_pause_blur.cpp
  src/clean_pause_blur.h
  src/clean_pause_bubbles.cpp
  src/clean_pause_bubbles.h
  src/kcd2_abi.h
  src/process_guard.cpp
  src/process_guard.h
)

function(configure_clean_pause_target target)
  target_compile_definitions(${target} PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    UNICODE
    _UNICODE
  )

  target_compile_options(${target} PRIVATE
    /W4
    /permissive-
    /EHsc
    /utf-8
  )

  target_link_libraries(${target} PRIVATE minhook)
  set_target_properties(${target} PROPERTIES PREFIX "")
endfunction()

# Standalone compatibility package. This remains a version.dll proxy so users
# who do not want a shared ASI loader can keep the retail-proven installation.
add_library(kcd2_clean_pause_version SHARED
  src/version_proxy.cpp
  src/version.def
  ${CLEAN_PAUSE_RUNTIME_SOURCES}
)
configure_clean_pause_target(kcd2_clean_pause_version)
set_target_properties(kcd2_clean_pause_version PROPERTIES OUTPUT_NAME "version")

# Shared-loader package. An ASI file is a normal Windows DLL loaded by an ASI
# loader; it uses the exact same Clean Pause runtime and only replaces the
# version.dll proxy bootstrap with a minimal DllMain entry point.
add_library(kcd2_clean_pause_asi SHARED
  src/asi_entry.cpp
  ${CLEAN_PAUSE_RUNTIME_SOURCES}
)
configure_clean_pause_target(kcd2_clean_pause_asi)
set_target_properties(kcd2_clean_pause_asi PROPERTIES
  OUTPUT_NAME "KCD2CleanPause"
  SUFFIX ".asi"
)
