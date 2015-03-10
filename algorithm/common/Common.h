#ifndef SLP_COMMON_H
#define SLP_COMMON_H

#define BOTTOM (-1)

#define ARRAY_LENGTH(arr) (sizeof(arr) / sizeof(arr[0]))

#ifdef SLP_VERBOSE_DEBUG
#	define dbgverbose(...) dbg(__VA_ARGS__)
#else
#	define dbgverbose(...)
#endif

#define max(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   _a > _b ? _a : _b; })

#define min(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   _a < _b ? _a : _b; })

#define minbot(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   (_a == BOTTOM || _b < _a) ? _b : _a; })

#endif // SLP_COMMON_H
