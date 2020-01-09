#ifndef SLP_AVERAGE_H
#define SLP_AVERAGE_H

#include <stdint.h>

void incremental_average(uint32_t* __restrict current_average, uint32_t* __restrict current_seen, uint32_t value)
{
    if (*current_seen == 0)
    {
        *current_seen += 1;
        *current_average = value;
    }
    else
    {
        *current_seen += 1;

        if (value >= *current_average)
        {
            *current_average += (value - *current_average) / *current_seen;
        }
        else
        {
            *current_average -= (*current_average - value) / *current_seen;
        }
    }
}

#endif // SLP_AVERAGE_H
