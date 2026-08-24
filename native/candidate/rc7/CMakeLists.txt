cmake_minimum_required(VERSION 3.24)
project(kcd2_clean_pause_rc7_candidate LANGUAGES C CXX)

if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "The rc7 candidate targets 64-bit Windows/MSVC only.")
endif()
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "KCD2 Clean Pause requires a 64-bit build.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>" CACHE STRING "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(RC7_GENERATED_SOURCE "${CMAKE_CURRENT_BINARY_DIR}/clean_pause_candidate_v2.generated.cpp")
execute_process(
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/generate_candidate_v2.py"
          "${CMAKE_CURRENT_SOURCE_DIR}/clean_pause_candidate.cpp" "${RC7_GENERATED_SOURCE}"
  RESULT_VARIABLE RC7_GENERATE_RESULT
  OUTPUT_VARIABLE RC7_GENERATE_OUTPUT
  ERROR_VARIABLE RC7_GENERATE_ERROR
)
if(NOT RC7_GENERATE_RESULT EQUAL 0)
  message(FATAL_ERROR "Failed to generate rc7b source: ${RC7_GENERATE_ERROR}")
endif()
message(STATUS "${RC7_GENERATE_OUTPUT}")

include(FetchContent)
FetchContent_Declare(
  minhook
  GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
  GIT_TAG v1.3.4
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(minhook)

add_library(kcd2_clean_pause_rc7_candidate SHARED
  ../../src/version_proxy.cpp
  ../../src/version.def
  "${RC7_GENERATED_SOURCE}"
  ../../src/clean_pause_native.h
  ../../src/kcd2_abi.h
)

target_include_directories(kcd2_clean_pause_rc7_candidate PRIVATE ../../src)
target_compile_definitions(kcd2_clean_pause_rc7_candidate PRIVATE
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  UNICODE
  _UNICODE
)
target_compile_options(kcd2_clean_pause_rc7_candidate PRIVATE
  /W4
  /permissive-
  /EHsc
  /utf-8
)
target_link_libraries(kcd2_clean_pause_rc7_candidate PRIVATE minhook)
set_target_properties(kcd2_clean_pause_rc7_candidate PROPERTIES
  OUTPUT_NAME "version"
  PREFIX ""
)
