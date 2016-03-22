#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channels
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	FAKE_CHANNEL = 3,
	BEACON_CHANNEL = 4,
	DUMMYNORMAL_CHANNEL = 5,
};

#define BOTTOM (-1)
#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 6
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 10

#endif // SLP_CONSTANTS_H
