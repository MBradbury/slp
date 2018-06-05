#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

#define MESSAGE_QUEUE_SIZE 15

enum Channel
{
	NORMAL_CHANNEL = 1,
    DISSEM_CHANNEL = 2,
    EMPTYNORMAL_CHANNEL = 3,
};

enum
{
    SourceNode = 0,
    SinkNode = 1,
    NormalNode = 2,
};

#define SLP_MAX_NUM_SOURCES 1
#define SLP_MAX_NUM_SINKS 1
#define SLP_MAX_1_HOP_NEIGHBOURHOOD 5
#define SLP_MAX_2_HOP_NEIGHBOURHOOD 13

#endif // SLP_CONSTANTS_H
