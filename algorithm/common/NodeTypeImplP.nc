
#include "MetricLogging.h"

generic module NodeTypeImplP(uint8_t maximum_node_types)
{
	provides interface NodeType;

	uses interface MetricLogging;

#ifdef USE_SERIAL_PRINTF
	uses interface LocalTime<TMilli>;
#endif
}
implementation
{
	uint8_t idents[maximum_node_types];
	const char* names[maximum_node_types];

	uint8_t size = 0;

	uint8_t current_type;

	command bool NodeType.register_pair(uint8_t ident, const char* name)
	{
		if (size < maximum_node_types)
		{
			idents[size] = ident;
			names[size] = name;

			++size;

			return TRUE;
		}
		else
		{
			ERROR_OCCURRED(ERROR_TOO_MANY_NODE_TYPES, "Not enough room for %s, Please increase the size of NodeTypeP.\n", name);
			return FALSE;
		}
	}

	command uint8_t NodeType.from_string(const char* name)
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

	command const char* NodeType.to_string(uint8_t ident)
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

	command const char* NodeType.current_to_string()
	{
		return call NodeType.to_string(current_type);
	}

	command void NodeType.init(uint8_t ident)
	{
		METRIC_NODE_CHANGE((uint8_t)-1, "<unknown>", ident, call NodeType.to_string(ident));

		current_type = ident;
	}

	command void NodeType.set(uint8_t ident)
	{
		if (current_type != ident)
		{
			METRIC_NODE_CHANGE(current_type, call NodeType.to_string(current_type), ident, call NodeType.to_string(ident));

			current_type = ident;
		}
	}

	command uint8_t NodeType.get()
	{
		return current_type;
	}
}
