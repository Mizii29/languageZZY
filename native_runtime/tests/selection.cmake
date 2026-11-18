execute_process(COMMAND "${EXE}" "unknown" RESULT_VARIABLE result
  OUTPUT_VARIABLE output ERROR_VARIABLE error TIMEOUT 5)
if(NOT result STREQUAL "1" OR NOT output STREQUAL "" OR NOT error MATCHES "no Program cases selected")
  message(FATAL_ERROR "empty Program selection must fail: ${result}: ${output}: ${error}")
endif()
