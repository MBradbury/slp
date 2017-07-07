#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channels
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	DISABLE_CHANNEL = 3,
	ACTIVATE_CHANNEL = 4,
	BEACON_CHANNEL = 5,
	POLL_CHANNEL = 6,
};

#define SLP_MAX_NUM_SOURCES 1
#define SLP_MAX_NUM_SINKS 1

#define SLP_MAX_1_HOP_NEIGHBOURHOOD 10

#define AWAY_DELAY_MS 200

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (5 * 1000)

#define CONE_WIDTH 3

typedef struct
{
	int16_t sink_distance;
	int16_t source_distance;
} ni_container_t;

#endif // SLP_CONSTANTS_H
