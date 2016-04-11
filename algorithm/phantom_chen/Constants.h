#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channels
{
	NORMAL_CHANNEL = 1,
};

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20

#define NORTH_WEST_DIRECTION 0
#define NORTH_EAST_DIRECTION 1
#define SOUTH_WEST_DIRECTION 2
#define SOUTH_EAST_DIRECTION 3
#define BIASED_X_AXIS        4
#define BIASED_Y_AXIS        5

//define the global vaiable.
//make it work for multiple sources.
uint16_t message_no = 1;

#endif // SLP_CONSTANTS_H

