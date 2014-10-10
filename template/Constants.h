#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

/*#ifndef SOURCE_PERIOD_MS
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
#endif*/

enum Channels
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	CHOOSE_CHANNEL = 3,
	FAKE_CHANNEL = 4
};

#define BOTTOM (-1)

#endif // SLP_CONSTANTS_H
