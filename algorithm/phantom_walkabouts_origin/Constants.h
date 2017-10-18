#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	BEACON_CHANNEL = 3
};

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 16
#define SLP_MAX_NUM_AWAY_MESSAGES 4
#define CENTRE_AREA 5 		//hops from the real cenre
#define MAX_NUM_NEIGHBOURS 2 //max neighbours each direction

#define BOTTOMLEFT 0
#define BOTTOMRIGHT 1
#define SINK 2
#define TOPRIGHT 3

#endif // SLP_CONSTANTS_H
