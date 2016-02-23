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

#define minbot(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   (_a == BOTTOM ? _b : (_b == BOTTOM ? _a : (_b < _a ? _b : _a))); })

/*
#define simdbg(...) dbg(__VA_ARGS__)
#define simdbg_clear(...) dbg_clear(__VA_ARGS__)
#define simdbgerror(...) dbgerror(__VA_ARGS__)
#define simdbgerror_clear(...) dbgerror_clear(__VA_ARGS__)
*/

#endif // SLP_COMMON_H
