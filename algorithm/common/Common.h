#ifndef SLP_COMMON_H
#define SLP_COMMON_H

#define BOTTOM (-1)

#define ARRAY_LENGTH(arr) (sizeof(arr) / sizeof(arr[0]))

#define max(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   _a > _b ? _a : _b; })

#define min(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   _a < _b ? _a : _b; })

#define min3(a, b, c) \
	({ __typeof__(a) _m1 = min(a, b), _c = (c); \
	   _m1 < _c ? _m1 : _c; })

#define minbot(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   (_a == BOTTOM ? _b : (_b == BOTTOM ? _a : (_b < _a ? _b : _a))); })


inline int16_t botinc(int16_t x)
{
	return x == BOTTOM ? BOTTOM : x + 1;
}

inline double rad2deg(double r)
{
	return r * (180.0 / M_PI);
}

// Compiling for testbeds, so need to route the simdbg to the printf library
#ifdef USE_SERIAL_PRINTF

#define NEW_PRINTF_SEMANTICS
#include "printf.h"

#define simdbg(name, ...) printf(__VA_ARGS__); printfflush()
#define simdbg_clear(name, ...) printf(__VA_ARGS__); printfflush()
#define simdbgerror(name, ...) printf(__VA_ARGS__); printfflush()
#define simdbgerror_clear(name, ...) printf(__VA_ARGS__); printfflush()

#define PRIu8 "u"
#define PRIu64 "llu"
#define PRIi64 "lld"

// TODO: Implement these time strings
#define sim_time_string() "<TODO implement sim_time_string>"
#define sim_time() 0ULL

#endif

#ifdef SLP_VERBOSE_DEBUG
#	define simdbgverbose(...) simdbg(__VA_ARGS__)
#else
#	define simdbgverbose(...)
#endif

#endif // SLP_COMMON_H
