#ifndef SLP_BLOOM_FILTER
#define SLP_BLOOM_FILTER

#include "pp.h"

// Adapted From: http://en.literateprograms.org/Bloom_filter_%28C%29

typedef nx_struct bloom_filter
{
	nx_uint8_t data[4];

} nx_bloom_filter_t;

typedef nx_bloom_filter_t bloom_filter_t;

#define BLOOM_MAX_BITS (sizeof(bloom_filter_t) * CHAR_BIT)

void bloom_filter_clear(bloom_filter_t* bloom);
void bloom_filter_add(bloom_filter_t* bloom, uint16_t data);
bool bloom_filter_test(const bloom_filter_t* bloom, uint16_t data);

#endif
