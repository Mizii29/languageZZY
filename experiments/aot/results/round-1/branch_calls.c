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
static int64_t f1(int64_t);

static int64_t f0(int64_t v0) {
    int64_t t1 = INT64_C(2);
    int64_t t2 = zzy_mod(v0, t1);
    int64_t t3 = INT64_C(0);
    bool t4 = t2 == t3;
    if (t4) {
        int64_t t5 = INT64_C(1);
        int64_t t6 = zzy_add(v0, t5);
        return t6;
    }
    int64_t t7 = INT64_C(1);
    int64_t t8 = zzy_sub(v0, t7);
    return t8;
}

static int64_t f1(int64_t v9) {
    int64_t t10 = INT64_C(0);
    int64_t v11 = t10;
    int64_t t12 = INT64_C(0);
    int64_t v13 = t12;
    while (true) {
        bool t14 = v11 < v9;
        if (!t14) break;
        int64_t t15 = f0(v11);
        int64_t t16 = zzy_add(v13, t15);
        v13 = t16;
        int64_t t17 = INT64_C(1);
        int64_t t18 = zzy_add(v11, t17);
        v11 = t18;
    }
    return v13;
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
        result = f1(n);
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
