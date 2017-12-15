#ifndef SLP_SEQNOWITHFLAG_H
#define SLP_SEQNOWITHFLAG_H

#include "SequenceNumber.h"

typedef struct
{
	SequenceNumber seq_no;
	am_addr_t addr;
	uint8_t flag;
} SeqNoWithFlag;

typedef struct
{
	SequenceNumber seq_no;
	am_addr_t addr;
} SeqNoWithAddr;

#endif // SLP_SEQNOWITHFLAG_H