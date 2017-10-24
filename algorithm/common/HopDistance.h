#ifndef SLP_HOP_DISTANCE_H
#define SLP_HOP_DISTANCE_H

typedef int16_t hop_distance_t;
typedef nx_int16_t nx_hop_distance_t;

#define HOP_DISTANCE_SPEC "%" PRIi16

#define UNKNOWN_HOP_DISTANCE (-1)

inline hop_distance_t hop_distance_increment_nocheck(hop_distance_t x)
{
    return x <= UNKNOWN_HOP_DISTANCE ? UNKNOWN_HOP_DISTANCE : x + 1;
}

inline hop_distance_t hop_distance_min_nocheck(hop_distance_t a, hop_distance_t b)
{
    if (a <= UNKNOWN_HOP_DISTANCE && b <= UNKNOWN_HOP_DISTANCE)
    {
        return UNKNOWN_HOP_DISTANCE;
    }

    return a <= UNKNOWN_HOP_DISTANCE ? b : (b <= UNKNOWN_HOP_DISTANCE ? a : (b < a ? b : a));
}

#define hop_distance_increment(x) hop_distance_increment_nocheck(x)
#define hop_distance_min(a, b) hop_distance_min_nocheck(a, b)

#endif // SLP_HOP_DISTANCE_H
