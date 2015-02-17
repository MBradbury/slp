#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

#ifdef DEFAULT_PARAMETERS
#ifndef SOURCE_PERIOD_MS
#	define SOURCE_PERIOD_MS (1000)
#endif

#ifndef FAKE_PERIOD_MS
#	define FAKE_PERIOD_MS (1000)
#endif

#ifndef SOURCE_NODE_ID
#	define	SOURCE_NODE_ID (0)
#endif

#ifndef SINK_NODE_ID
#	define SINK_NODE_ID (60)
#endif
#endif

enum Channels
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	CHOOSE_CHANNEL = 3,
	FAKE_CHANNEL = 4
};

#define BOTTOM (-1)

#define ARRAY_LENGTH(arr) (sizeof(arr) / sizeof(arr[0]))

#ifdef SLP_VERBOSE_DEBUG
#	define dbgverbose(...) dbg(__VA_ARGS__)
#else
#	define dbgverbose(...)
#endif

#define max(a, b) \
	({ const __typeof__(a) _a = (a), _b = (b); \
	   _a > _b ? _a : _b; })

#define min(a, b) \
	({ const __typeof__(a) _a = (a), _b = (b); \
	   _a < _b ? _a : _b; })

#define minbot(a, b) \
	({ const __typeof__(a) _a = (a), _b = (b); \
	   (_a == BOTTOM || _b < _a) ? _b : _a; })

#endif // SLP_CONSTANTS_H
