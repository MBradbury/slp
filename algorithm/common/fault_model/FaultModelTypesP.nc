
#include "MetricLogging.h"

generic module FaultModelTypesP(uint8_t maximum_fault_point_types)
{
    provides interface FaultModelTypes;
    provides interface Init;

    uses interface MetricLogging;
}
implementation
{
	uint8_t idents[maximum_fault_point_types];
    const char* names[maximum_fault_point_types];

    uint8_t size;

    command error_t Init.init()
    {
        size = 0;

        return SUCCESS;
    }

    command bool FaultModelTypes.register_pair(uint8_t ident, const char* name)
    {
        const size_t name_length = strlen(name) + 1;

        if (name_length > MAXIMUM_FAULT_POINT_TYPE_NAME_LENGTH)
        {
            ERROR_OCCURRED(ERROR_FAULT_POINT_NAME_TOO_LONG,
            	"The fault point %s is too long (%zu), please make it shorter than %u.\n",
                name, name_length, MAXIMUM_FAULT_POINT_TYPE_NAME_LENGTH);
            return FALSE;
        }

        if (size < maximum_fault_point_types)
        {
            idents[size] = ident;
            names[size] = name;

            ++size;

            METRIC_FAULT_POINT_TYPE_ADD(ident, name);

            return TRUE;
        }
        else
        {
            ERROR_OCCURRED(ERROR_TOO_MANY_FAULT_POINT_TYPES,
            	"Not enough room for %s, Please increase the size of FaultModelTypes.\n",
            	name);
            return FALSE;
        }
    }

    command uint8_t FaultModelTypes.from_string(const char* name)
    {
        uint8_t i;
        for (i = 0; i != size; ++i)
        {
            if (strcmp(names[i], name) == 0)
            {
                return idents[i];
            }
        }

        return (uint8_t)-1;
    }

    command const char* FaultModelTypes.to_string(uint8_t ident)
    {
        uint8_t i;
        for (i = 0; i != size; ++i)
        {
            if (idents[i] == ident)
            {
                return names[i];
            }
        }

        return "<unknown>";
    }
}
