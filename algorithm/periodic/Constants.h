#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

#define MESSAGE_QUEUE_SIZE 15

enum Channel
{
	NORMAL_CHANNEL = 1,
	DUMMY_NORMAL_CHANNEL = 2
};

#define SLP_MAX_NUM_SOURCES 20

// Disable using CRC checks
#define SLP_NO_CRC_CHECKS

#endif // SLP_CONSTANTS_H