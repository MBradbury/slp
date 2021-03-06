#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

#define MESSAGE_QUEUE_SIZE 15

enum Channel
{
	NORMAL_CHANNEL = 1,
    DISSEM_CHANNEL = 2,
    SEARCH_CHANNEL = 3,
    CHANGE_CHANNEL = 4,
    EMPTYNORMAL_CHANNEL = 5
};

enum
{
    SourceNode = 0,
    SinkNode = 1,
    NormalNode = 2,
    SearchNode = 3,
    ChangeNode = 4,
};

#define SLP_MAX_NUM_SOURCES 1
#define SLP_MAX_NUM_SINKS 1
//#define SLP_MAX_1_HOP_NEIGHBOURHOOD 5
//#define SLP_MAX_2_HOP_NEIGHBOURHOOD 13
//For low-asymmetry, could have diagonal neighbours
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 9
#define SLP_MAX_2_HOP_NEIGHBOURHOOD 25

#endif // SLP_CONSTANTS_H
