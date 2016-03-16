#ifndef SLP_SEQUENCENUMBER_H
#define SLP_SEQUENCENUMBER_H

typedef uint32_t SequenceNumber;
typedef nx_uint32_t NXSequenceNumber;

inline void sequence_number_init(SequenceNumber* seqno) __attribute__((nonnull(1)))
{
	*seqno = 0;
}

inline SequenceNumber sequence_number_get(const SequenceNumber* seqno) __attribute__((nonnull(1)))
{
	return *seqno;
}

inline SequenceNumber sequence_number_next(const SequenceNumber* seqno) __attribute__((nonnull(1)))
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
