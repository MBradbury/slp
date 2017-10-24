#ifndef SLP_HOP_DISTANCE_DEBUG_H
#define SLP_HOP_DISTANCE_DEBUG_H

hop_distance_t hop_distance_min_check(hop_distance_t a, hop_distance_t b, const char* file, int line)
{
    if (a < UNKNOWN_HOP_DISTANCE || b < UNKNOWN_HOP_DISTANCE)
    {
        ERROR_OCCURRED(0, "Bad minbot setting %" PRIi16 " or %" PRIi16 " In %s at %d\n", a, b, file, line);
    }

    return hop_distance_min_nocheck(a, b);
}

hop_distance_t hop_distance_increment_check(hop_distance_t a, const char* file, int line)
{
    if (a < UNKNOWN_HOP_DISTANCE)
    {
        ERROR_OCCURRED(0, "Bad botinc setting %" PRIi16 " In %s at %d\n", a, file, line);
    }

    return hop_distance_increment_nocheck(a);
}

#undef hop_distance_min
#undef hop_distance_increment

#define hop_distance_min(a, b) hop_distance_min_check(a, b, __FILE__, __LINE__)
#define hop_distance_increment(a) hop_distance_increment_check(a, __FILE__, __LINE__)

#endif // SLP_HOP_DISTANCE_DEBUG_H
