#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	CHOOSE_CHANNEL = 3,
	FAKE_CHANNEL = 4,
    NOTIFY_CHANNEL = 5,
};

enum NodeType
{
    SourceNode = 0,
    SinkNode = 1,
    NormalNode = 2,
    TempFakeNode = 3,
    PermFakeNode = 4,
};

#define BOTTOM (-1)

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (4 * 1000)

#define SINK_AWAY_MESSAGES_TO_SEND 2

#define CHOOSE_RTX_LIMIT_FOR_FS 5

#endif // SLP_CONSTANTS_H
