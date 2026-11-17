/* Generated from ZZY's prepared AST. Int64 AOT pilot; not full ZZY. */
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#endif

static void zzy_fail(const char *message) {
    fprintf(stderr, "AOT subset error: %s\n", message);
    exit(1);
}
static inline int64_t zzy_add(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_add_overflow(a, b, &r)) zzy_fail("Int64 overflow");
    return r;
}
static inline int64_t zzy_sub(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_sub_overflow(a, b, &r)) zzy_fail("Int64 overflow");
    return r;
}
static inline int64_t zzy_mul(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_mul_overflow(a, b, &r)) zzy_fail("Int64 overflow");
    return r;
}
static inline int64_t zzy_neg(int64_t a) {
    return zzy_sub(INT64_C(0), a);
}
static inline int64_t zzy_mod(int64_t a, int64_t b) {
    if (b == 0) zzy_fail("division by zero");
    if (a == INT64_MIN && b == -1) return 0;
    int64_t r = a % b;
    if (r && ((r < 0) != (b < 0))) r = zzy_add(r, b);
    return r;
}
static int64_t parse_int(const char *text) {
    char *end;
    errno = 0;
    intmax_t value = strtoimax(text, &end, 10);
    if (errno || end == text || *end || value < INT64_MIN || value > INT64_MAX)
        zzy_fail("argument must be Int64");
    return (int64_t)value;
}

static int64_t f0(int64_t);

static int64_t f0(int64_t v0) {
    int64_t t1 = INT64_C(0);
    int64_t v2 = t1;
    int64_t t3 = INT64_C(0);
    int64_t v4 = t3;
    while (true) {
        bool t5 = v2 < v0;
        if (!t5) break;
        int64_t t6 = zzy_mul(v2, v2);
        int64_t t7 = zzy_add(v4, t6);
        v4 = t7;
        int64_t t8 = INT64_C(1);
        int64_t t9 = zzy_add(v2, t8);
        v2 = t9;
    }
    return v4;
}

int main(int argc, char **argv) {
    if (argc != 2 && argc != 3) zzy_fail("usage: program N [REPEAT]");
    volatile int64_t n = parse_int(argv[1]);
    int64_t repeat = argc == 3 ? parse_int(argv[2]) : 1;
    if (repeat < 1 || repeat > 100000) zzy_fail("REPEAT must be 1..100000");
    int64_t result = 0, checksum = 0;
#ifdef _WIN32
    LARGE_INTEGER frequency, started, ended;
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&started);
#endif
    for (int64_t k = 0; k < repeat; ++k) {
        result = f0(n);
        checksum = zzy_add(checksum, result);
    }
#ifdef _WIN32
    QueryPerformanceCounter(&ended);
    uint64_t elapsed = (uint64_t)((ended.QuadPart - started.QuadPart) * 1000000000ULL
                                  / (uint64_t)frequency.QuadPart);
    PROCESS_MEMORY_COUNTERS counters;
    counters.cb = sizeof(counters);
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof(counters)))
        zzy_fail("memory measurement failed");
    fprintf(stderr, "EXECUTE_NS=%" PRIu64 "\nPEAK_WORKING_SET_BYTES=%" PRIu64 "\n",
            elapsed, (uint64_t)counters.PeakWorkingSetSize);
#endif
    if (repeat == 1) printf("%" PRId64 "\n", result);
    else printf("%" PRId64 " %" PRId64 "\n", result, checksum);
    return 0;
}
