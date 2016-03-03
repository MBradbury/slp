#ifndef SLP_COMMON_H
#define SLP_COMMON_H

#define BOTTOM (-1)

#define ARRAY_LENGTH(arr) (sizeof(arr) / sizeof(arr[0]))

#ifdef SLP_VERBOSE_DEBUG
#	define simdbgverbose(...) simdbg(__VA_ARGS__)
#else
#	define simdbgverbose(...)
#endif

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

/*
#define simdbg(...) dbg(__VA_ARGS__)
#define simdbg_clear(...) dbg_clear(__VA_ARGS__)
#define simdbgerror(...) dbgerror(__VA_ARGS__)
#define simdbgerror_clear(...) dbgerror_clear(__VA_ARGS__)
*/

#endif // SLP_COMMON_H
