#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channels
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	BEACON_CHANNEL = 3
};

typedef enum
{
	UnknownSinkLocation, Centre, Others 
}SinkLocation;

typedef enum
{
	UnknownBiasType, H, V 
}BiasedType;

typedef enum
{
	UnknownMessageType, ShortRandomWalk, LongRandomWalk
}WalkType;

enum
{
	SourceNode, SinkNode, NormalNode
};

typedef enum
{
	UnknownSet = 0, CloserSet = (1 << 0), FurtherSet = (1 << 1), CloserSideSet = (1 << 2), FurtherSideSet = (1 << 3)
}SetType;

#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_NUM_SOURCES 20
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 16
#define SLP_MAX_NUM_AWAY_MESSAGES 4
#define MAX_NUM_NEIGHBOURS 2 //max neighbours each direction

#define BOTTOMLEFT 0
#define BOTTOMRIGHT 1
#define SINK 2

#define ALPHA 10
#define ALPHA_RETRY 10
#define RTX_ATTEMPTS 20

#define SourceCorner 1
#define Source2CornerTop 2
#define Source3CornerTop 3
#define SinkCorner 4
#define SinkCorner2Source 5
#define SinkCorner3Source 6

#endif // SLP_CONSTANTS_H