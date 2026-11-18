execute_process(COMMAND "${EXE}" "unknown" RESULT_VARIABLE result
  OUTPUT_VARIABLE output ERROR_VARIABLE error TIMEOUT 5)
if(NOT result STREQUAL "1" OR NOT output STREQUAL "" OR NOT error STREQUAL "nonempty named selection required\n")
  message(FATAL_ERROR "empty runtime selection must fail: ${result}: ${output}: ${error}")
endif()
