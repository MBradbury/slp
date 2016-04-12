#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channels
{
	NORMAL_CHANNEL = 1,
};

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20

#define NORTH_WEST_DIRECTION 0
#define NORTH_EAST_DIRECTION 1
#define SOUTH_WEST_DIRECTION 2
#define SOUTH_EAST_DIRECTION 3
#define BIASED_X_AXIS        4
#define BIASED_Y_AXIS        5

#define SHORT_RANDOM_WALK 0
#define LONG_RANDOM_WALK 1

//define the global vaiable.
//make it work for multiple sources.
uint16_t message_no = 1;
uint16_t current_message = 0;
uint16_t previous_message = 0;

#endif // SLP_CONSTANTS_H

