
#include "MetricLogging.h"

generic module MessageTypeImplP(uint8_t maximum_message_types)
{
	provides interface MessageType;

	uses interface MetricLogging;
}
implementation
{
	uint8_t idents[maximum_message_types];
	const char* names[maximum_message_types];

	uint8_t size = 0;

	command bool MessageType.register_pair(uint8_t ident, const char* name)
	{
		if (size < maximum_message_types)
		{
			idents[size] = ident;
			names[size] = name;

			++size;

			METRIC_MESSAGE_TYPE_ADD(ident, name);

			return TRUE;
		}
		else
		{
			ERROR_OCCURRED(ERROR_TOO_MANY_MESSAGE_TYPES, "Not enough room for %s, Please increase the size of MessageTypeP.\n", name);
			return FALSE;
		}
	}

	command uint8_t MessageType.from_string(const char* name)
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

	command const char* MessageType.to_string(uint8_t ident)
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
