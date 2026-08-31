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
option(CLEAN_PAUSE_BUILD_RUNTIME_TESTS "Build executable runtime-profile tests" OFF)

file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../VERSION" CLEAN_PAUSE_VERSION)
string(STRIP "${CLEAN_PAUSE_VERSION}" CLEAN_PAUSE_VERSION)
find_package(Git QUIET)
set(CLEAN_PAUSE_BUILD_ID "unknown")
if(GIT_FOUND)
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" rev-parse --short=12 HEAD
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/.."
    OUTPUT_VARIABLE CLEAN_PAUSE_BUILD_ID
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE CLEAN_PAUSE_GIT_RESULT
  )
  if(NOT CLEAN_PAUSE_GIT_RESULT EQUAL 0 OR CLEAN_PAUSE_BUILD_ID STREQUAL "")
    set(CLEAN_PAUSE_BUILD_ID "unknown")
  endif()
endif()

include(FetchContent)
FetchContent_Declare(
  minhook
  GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
  # MinHook v1.3.4, pinned to the immutable commit behind the release tag.
  GIT_TAG c3fcafdc10146beb5919319d0683e44e3c30d537
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(minhook)

set(CLEAN_PAUSE_RUNTIME_SOURCES
  # Production entry compiles the mature runtime through a small profiled wrapper
  # that replaces only build gating/environment discovery. Do not compile
  # clean_pause_native.cpp separately: it is included by this translation unit.
  src/clean_pause_native_profiled.cpp
  src/clean_pause_native.h
  src/clean_pause_blur.cpp
  src/clean_pause_blur.h
  src/clean_pause_bubbles.cpp
  src/clean_pause_bubbles.h
  src/clean_pause_hud_mask.cpp
  src/clean_pause_hud_mask.h
  src/kcd2_abi.h
  src/kcd2_runtime_profile.cpp
  src/kcd2_runtime_profile.h
  src/process_guard.cpp
  src/process_guard.h
)

function(configure_clean_pause_target target)
  target_compile_definitions(${target} PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    UNICODE
    _UNICODE
    CLEAN_PAUSE_VERSION="${CLEAN_PAUSE_VERSION}"
    CLEAN_PAUSE_BUILD_ID="${CLEAN_PAUSE_BUILD_ID}"
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

if(CLEAN_PAUSE_BUILD_RUNTIME_TESTS)
  enable_testing()
  add_executable(kcd2_runtime_profile_tests
    tests/runtime_profile_tests.cpp
    src/kcd2_runtime_profile.cpp
    src/kcd2_runtime_profile.h
    src/kcd2_abi.h
  )
  target_include_directories(kcd2_runtime_profile_tests PRIVATE src)
  target_compile_definitions(kcd2_runtime_profile_tests PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    UNICODE
    _UNICODE
  )
  target_compile_options(kcd2_runtime_profile_tests PRIVATE
    /W4
    /permissive-
    /EHsc
    /utf-8
  )
  add_test(NAME runtime-profile COMMAND kcd2_runtime_profile_tests)
endif()
