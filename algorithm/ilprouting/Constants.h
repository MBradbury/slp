#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

#include "HopDistance.h"

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	BEACON_CHANNEL = 3,
	POLL_CHANNEL = 4,
};

enum NodeType
{
    SourceNode = 0,
    SinkNode = 1,
    NormalNode = 2,
};

#define SLP_MAX_NUM_SOURCES 5
#define SLP_MAX_NUM_SINKS 1

#define SLP_MAX_1_HOP_NEIGHBOURHOOD 10


// The amount of time in ms that it takes to send a message from one node to another
#define ALPHA 10
#define ALPHA_RETRY 20

#define SINK_AWAY_MESSAGES_TO_SEND 2
#define SINK_AWAY_DELAY_MS (1 * 1000)
#define AWAY_RETRY_SEND_DELAY 65

#define NORMAL_ROUTE_FROM_SINK_DISTANCE_LIMIT 4

#define RTX_ATTEMPTS 9
#define BAD_NEIGHBOUR_THRESHOLD 3
#define BAD_NEIGHBOUR_DO_SEARCH_THRESHOLD 5

#define CALCULATE_TARGET_ATTEMPTS 5
#define NO_NEIGHBOURS_DO_POLL_THRESHOLD 3

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (4 * 1000)

typedef struct
{
	hop_distance_t sink_distance;
	hop_distance_t source_distance;
	uint16_t backtracks_from;
} ni_container_t;

enum ApplicationSLPErrorCodes
{
	ERROR_RTX_FAILED = 1001,
	ERROR_RTX_FAILED_TRYING_OTHER = 1002,

    ERROR_UNKNOWN_MSG_STAGE = 1003,
    ERROR_NO_ROUTE_TO_SINK = 1004,
    ERROR_FAILED_TO_FIND_MSG_ROUTE = 1005,
    ERROR_FAILED_CHOOSE_MSG = 1006,
    ERROR_NO_NEIGHBOURS = 1007,
    //ERROR_NO_MESSAGES = 1008,
    ERROR_FAILED_TO_SEND_NORMAL = 1009,
};

enum ApplicationSLPEvents
{
    ILPROUTING_EVENT_SEND_POLL = 3001,
    ILPROUTING_NO_MESSAGES = 3002,
};

enum GenericMetrics
{
    METRIC_GENERIC_TIME_TAKEN_TO_SEND = 1,
};

#endif // SLP_CONSTANTS_H
