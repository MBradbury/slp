#ifndef SLP_SEQUENCENUMBER_H
#define SLP_SEQUENCENUMBER_H

typedef uint64_t SequenceNumber;

inline void sequence_number_init(SequenceNumber* seqno) __attribute__((nonnull(1)))
{
	*seqno = 0;
}

inline uint32_t sequence_number_get(const SequenceNumber* seqno) __attribute__((nonnull(1)))
{
	return *seqno;
}

inline uint32_t sequence_number_next(const SequenceNumber* seqno) __attribute__((nonnull(1)))
{
	return *seqno + 1;
}

inline void sequence_number_increment(SequenceNumber* seqno) __attribute__((nonnull(1)))
{
	*seqno += 1;
}

inline bool sequence_number_before(const SequenceNumber* left, const SequenceNumber right) __attribute__((nonnull(1)))
{
	return *left < right;
}

inline void sequence_number_update(SequenceNumber* left, const SequenceNumber right) __attribute__((nonnull(1)))
{
	*left = right;
}

#endif // SLP_SEQUENCENUMBER_H
