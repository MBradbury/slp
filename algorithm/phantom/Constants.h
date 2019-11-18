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

#define AWAY_SEND_PERIOD (1 * 1000)

enum AppEventCodes
{
    METRIC_GENERIC_PATH_END = 3001,
    METRIC_GENERIC_SOURCE_DROPPED = 3002,
    METRIC_GENERIC_PATH_DROPPED = 3003,
};

#endif // SLP_CONSTANTS_H
