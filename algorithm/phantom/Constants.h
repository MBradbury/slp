#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	BEACON_CHANNEL = 3
};

enum NodeType
{
    SourceNode = 0,
    SinkNode = 1,
    NormalNode = 2,
};

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 16

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (2 * 1000)

#define MAX_AWAY_FLOODS 3
#define AWAY_INITIAL_SEND_DELAY (1000) // latests node start time default
#define AWAY_SEND_PERIOD (500)

#define ALPHA 10
#define ALPHA_RETRY 20
#define RTX_ATTEMPTS 9

enum AppEventCodes
{
    METRIC_GENERIC_PATH_END = 3001,
    METRIC_GENERIC_SOURCE_DROPPED = 3002,
    METRIC_GENERIC_PATH_DROPPED = 3003,
    METRIC_GENERIC_DIRECTION = 3004,
};

enum ApplicationSLPErrorCodes
{
    ERROR_RTX_FAILED = 1001,
};

#endif // SLP_CONSTANTS_H
