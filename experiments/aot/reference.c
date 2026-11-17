/* Independent, hand-written C baseline for the same two integer algorithms. */
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#endif

static void fail(const char *message) {
    fprintf(stderr, "C reference error: %s\n", message);
    exit(1);
}

static inline int64_t checked_add(int64_t a, int64_t b) {
    int64_t result;
    if (__builtin_add_overflow(a, b, &result)) fail("Int64 overflow");
    return result;
}

static inline int64_t checked_sub(int64_t a, int64_t b) {
    int64_t result;
    if (__builtin_sub_overflow(a, b, &result)) fail("Int64 overflow");
    return result;
}

static inline int64_t checked_mul(int64_t a, int64_t b) {
    int64_t result;
    if (__builtin_mul_overflow(a, b, &result)) fail("Int64 overflow");
    return result;
}

static int64_t sum_squares(int64_t n) {
    int64_t i = 0, total = 0;
    while (i < n) {
        total = checked_add(total, checked_mul(i, i));
        i = checked_add(i, 1);
    }
    return total;
}

static int64_t term(int64_t i) {
    if (i % 2 == 0) return checked_add(i, 1);
    return checked_sub(i, 1);
}

static int64_t branch_calls(int64_t n) {
    int64_t i = 0, total = 0;
    while (i < n) {
        total = checked_add(total, term(i));
        i = checked_add(i, 1);
    }
    return total;
}

static int64_t parse_int(const char *text) {
    char *end;
    errno = 0;
    intmax_t value = strtoimax(text, &end, 10);
    if (errno || end == text || *end || value < INT64_MIN || value > INT64_MAX)
        fail("argument must be Int64");
    return (int64_t)value;
}

int main(int argc, char **argv) {
    if (argc != 4) fail("usage: reference sum|branch N REPEAT");
    bool sum = strcmp(argv[1], "sum") == 0;
    if (!sum && strcmp(argv[1], "branch") != 0) fail("unknown case");
    volatile int64_t n = parse_int(argv[2]);
    int64_t repeat = parse_int(argv[3]);
    if (repeat < 1 || repeat > 100000) fail("REPEAT must be 1..100000");
    int64_t result = 0, checksum = 0;
#ifdef _WIN32
    LARGE_INTEGER frequency, started, ended;
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&started);
#endif
    for (int64_t k = 0; k < repeat; ++k) {
        result = sum ? sum_squares(n) : branch_calls(n);
        checksum = checked_add(checksum, result);
    }
#ifdef _WIN32
    QueryPerformanceCounter(&ended);
    uint64_t elapsed = (uint64_t)((ended.QuadPart - started.QuadPart) * 1000000000ULL
                                  / (uint64_t)frequency.QuadPart);
    PROCESS_MEMORY_COUNTERS counters;
    counters.cb = sizeof(counters);
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof(counters)))
        fail("memory measurement failed");
    fprintf(stderr, "EXECUTE_NS=%" PRIu64 "\nPEAK_WORKING_SET_BYTES=%" PRIu64 "\n",
            elapsed, (uint64_t)counters.PeakWorkingSetSize);
#endif
    printf("%" PRId64 " %" PRId64 "\n", result, checksum);
    return 0;
}
