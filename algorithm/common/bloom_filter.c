#include "bloom_filter.h"

// Adapted From: http://en.literateprograms.org/Bloom_filter_%28C%29

typedef uint16_t bloom_filter_size_t;

bool get_bit(const bloom_filter_t* bloom, bloom_filter_size_t bit)
{
	return (bloom->data[bit / CHAR_BIT] & (1 << (bit % CHAR_BIT))) != 0;
}

void set_bit(bloom_filter_t* bloom, bloom_filter_size_t bit)
{
	bloom->data[bit / CHAR_BIT] |= (1 << (bit % CHAR_BIT));
}

typedef uint32_t (*bloom_hash_t)(uint16_t);

typedef union
{
	uint16_t ui16;
	uint8_t ui8[2];

} hash_union_t;

uint32_t sax_hash(uint16_t data)
{
	uint32_t h = 0;

	hash_union_t u;
	u.ui16 = data;

	h ^= (h << 5) + (h >> 2) + u.ui8[0];
	h ^= (h << 5) + (h >> 2) + u.ui8[1];

	return h;
}

uint32_t sdbm_hash(uint16_t data)
{
	uint32_t h = 0;

	hash_union_t u;
	u.ui16 = data;

	h = u.ui8[0] + (h << 6) + (h << 16) - h;
	h = u.ui8[1] + (h << 6) + (h << 16) - h;

	return h;
}

static const bloom_hash_t bloom_hashes[] = { sax_hash, sdbm_hash };

void bloom_filter_clear(bloom_filter_t* bloom)
{
	memset(bloom, 0, sizeof(*bloom));
}

void bloom_filter_add(bloom_filter_t* bloom, uint16_t data)
{
	bloom_filter_size_t n;

	for (n = 0; n < ARRAY_SIZE(bloom_hashes); ++n)
	{
		set_bit(bloom, bloom_hashes[n](data) % BLOOM_MAX_BITS);
	}
}

bool bloom_filter_test(const bloom_filter_t* bloom, uint16_t data)
{
	bloom_filter_size_t n;

	for (n = 0; n < ARRAY_SIZE(bloom_hashes); ++n)
	{
		if (!get_bit(bloom, bloom_hashes[n](data) % BLOOM_MAX_BITS))
			return FALSE;
	}

	return TRUE;
}
