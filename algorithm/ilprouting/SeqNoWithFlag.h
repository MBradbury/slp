#ifndef SLP_SEQNOWITHFLAG_H
#define SLP_SEQNOWITHFLAG_H

#include "SequenceNumber.h"

// This struct needs to have no extra padding,
// This is so memcmp on the sizeof it will work.
typedef struct
{
	SequenceNumber seq_no; // 0  + 32 = 32
	am_addr_t addr;        // 32 + 16 = 48
	uint8_t flag;          // 48 +  8 = 56
	uint8_t padding;       // 56 +  8 = 64
} SeqNoWithFlag;

typedef struct
{
	SequenceNumber seq_no; // 0  + 32 = 32
	am_addr_t addr;        // 32 + 16 = 48
	uint16_t padding;      // 48 + 16 = 64
} SeqNoWithAddr;

// Make sure the size is as expected
STATIC_ASSERT(sizeof(SeqNoWithFlag) == 8);
STATIC_ASSERT(sizeof(SeqNoWithAddr) == 8);

#endif // SLP_SEQNOWITHFLAG_H
