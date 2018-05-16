#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channels
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	BEACON_CHANNEL = 3
};

enum
{
	SourceNode, SinkNode, NormalNode
};

enum
{
	SleepNode, OtherNode
};

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 16

#define SLEEP_NODE_HIGH_P 80
#define SLEEP_NODE_LOW_P 10

#endif // SLP_CONSTANTS_H
