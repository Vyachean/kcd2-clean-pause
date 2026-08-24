cmake_minimum_required(VERSION 3.24)
project(kcd2_clean_pause_pause_state_probe LANGUAGES C CXX)

if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "The diagnostic targets 64-bit Windows/MSVC only.")
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

add_library(kcd2_clean_pause_pause_state_probe SHARED
  ../src/version_proxy.cpp
  ../src/version.def
  pause_state_probe.cpp
  ../src/clean_pause_native.h
  ../src/kcd2_abi.h
)

target_include_directories(kcd2_clean_pause_pause_state_probe PRIVATE ../src)

target_compile_definitions(kcd2_clean_pause_pause_state_probe PRIVATE
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  UNICODE
  _UNICODE
)

target_compile_options(kcd2_clean_pause_pause_state_probe PRIVATE
  /W4
  /permissive-
  /EHsc
  /utf-8
)

target_link_libraries(kcd2_clean_pause_pause_state_probe PRIVATE minhook)

set_target_properties(kcd2_clean_pause_pause_state_probe PROPERTIES
  OUTPUT_NAME "version"
  PREFIX ""
)
