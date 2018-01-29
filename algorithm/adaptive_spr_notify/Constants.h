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

enum AppErrorCodes
{
    ErrorUnknownTempPeriodWait = 1001,
    ErrorUnknownPermPeriodWait = 1002,
    ErrorUnknownNormalPeriodWait = 1003,
};

enum AppEventCodes
{
    METRIC_GENERIC_DUTY_CYCLE_ON_NORMAL = 3001,
    METRIC_GENERIC_DUTY_CYCLE_ON_FAKE = 3002,
    METRIC_GENERIC_DUTY_CYCLE_ON_CHOOSE = 3003,
};

#define BOTTOM (-1)
#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 10
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 16

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (4 * 1000)

#define SINK_AWAY_MESSAGES_TO_SEND 3

#define CHOOSE_RTX_LIMIT_FOR_FS 5

#endif // SLP_CONSTANTS_H
