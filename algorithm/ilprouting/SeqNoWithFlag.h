#ifndef SLP_SEQNOWITHFLAG_H
#define SLP_SEQNOWITHFLAG_H

#include "SequenceNumber.h"

// This struct needs to have no extra padding,
// This is so memcmp on the sizeof it will work.
typedef struct
{
	SequenceNumber seq_no;
	am_addr_t addr;
	uint8_t flag;
	uint8_t padding;
} SeqNoWithFlag;

#endif // SLP_SEQNOWITHFLAG_H
