#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	CHOOSE_CHANNEL = 3,
	FAKE_CHANNEL = 4,
	BEACON_CHANNEL = 5,
	NOTIFY_CHANNEL = 6,
};

enum NodeType
{
    SourceNode = 0,
    SinkNode = 1,
    NormalNode = 2,
    TempFakeNode = 3,
    TailFakeNode = 4,
    PermFakeNode = 5,
};

#define BOTTOM (-1)
#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 16

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (3 * 1000)

#endif // SLP_CONSTANTS_H
