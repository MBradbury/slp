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

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (4 * 1000)
#define SINK_AWAY_MESSAGES_TO_SEND 3

#define AWAY_DELAY_MS 250

#endif // SLP_CONSTANTS_H
