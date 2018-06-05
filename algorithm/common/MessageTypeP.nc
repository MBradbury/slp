
#include "MetricLogging.h"

#define UNKNOWN_MESSAGE_TYPE UINT8_MAX

generic module MessageTypeP(uint8_t maximum_message_types)
{
	provides interface MessageType;
	provides interface Init;

	uses interface MetricLogging;
}
implementation
{
	uint8_t idents[maximum_message_types];
	const char* names[maximum_message_types];

	uint8_t size;

	command error_t Init.init()
	{
		size = 0;

		memset(idents, UNKNOWN_MESSAGE_TYPE, sizeof(idents));
		memset(names, 0, sizeof(names));

		return SUCCESS;
	}

	command bool MessageType.register_pair(uint8_t ident, const char* name)
	{
		const size_t name_length = strlen(name) + 1;

		if (name_length > MAXIMUM_MESSAGE_TYPE_NAME_LENGTH)
		{
			ERROR_OCCURRED(ERROR_MESSAGE_NAME_TOO_LONG, "The message type %s is too long (%zu), please make it shorter than %u.\n",
				name, name_length, MAXIMUM_MESSAGE_TYPE_NAME_LENGTH);
			return FALSE;
		}

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

#ifdef SLP_DEBUG
		ERROR_OCCURRED(ERROR_UNKNOWN_MESSAGE_TYPE, "Unable to convert message name %s (total %" PRIu8 ")\n", name, size);
#endif

		return UNKNOWN_MESSAGE_TYPE;
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

#ifdef SLP_DEBUG
		ERROR_OCCURRED(ERROR_UNKNOWN_MESSAGE_TYPE, "Unknown message type %" PRIu8 " (total %" PRIu8 ")\n", ident, size);
#endif

		return "<unknown>";
	}

	command uint8_t MessageType.unknown_type()
	{
		return UNKNOWN_MESSAGE_TYPE;
	}
}
