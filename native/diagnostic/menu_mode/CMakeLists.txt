cmake_minimum_required(VERSION 3.24)
project(kcd2_clean_pause_menu_mode_probe LANGUAGES C CXX)

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

add_library(kcd2_clean_pause_menu_mode_probe SHARED
  ../../src/version_proxy.cpp
  ../../src/version.def
  menu_mode_probe.cpp
  ../../src/clean_pause_native.h
  ../../src/kcd2_abi.h
)

target_include_directories(kcd2_clean_pause_menu_mode_probe PRIVATE ../../src)

target_compile_definitions(kcd2_clean_pause_menu_mode_probe PRIVATE
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  UNICODE
  _UNICODE
)

target_compile_options(kcd2_clean_pause_menu_mode_probe PRIVATE
  /W4
  /permissive-
  /EHsc
  /utf-8
)

set_target_properties(kcd2_clean_pause_menu_mode_probe PROPERTIES
  OUTPUT_NAME "version"
  PREFIX ""
)
