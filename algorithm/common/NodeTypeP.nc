
#include "MetricLogging.h"

#define UNKNOWN_NODE_TYPE UINT8_MAX

generic module NodeTypeP(uint8_t maximum_node_types)
{
	provides interface NodeType;
	provides interface Init;

	uses interface MetricLogging;
}
implementation
{
	uint8_t idents[maximum_node_types];
	const char* names[maximum_node_types];

	uint8_t size;

	uint8_t current_type;

	command error_t Init.init()
	{
		size = 0;

		current_type = UNKNOWN_NODE_TYPE;

		memset(idents, UNKNOWN_NODE_TYPE, sizeof(idents));
		memset(names, 0, sizeof(names));

		return SUCCESS;
	}

	command bool NodeType.register_pair(uint8_t ident, const char* name)
	{
		const size_t name_length = strlen(name) + 1;

		if (name_length > MAXIMUM_NODE_TYPE_NAME_LENGTH)
		{
			ERROR_OCCURRED(ERROR_NODE_NAME_TOO_LONG, "The node type %s is too long (%zu), please make it shorter than %u.\n",
				name, name_length, MAXIMUM_NODE_TYPE_NAME_LENGTH);
			return FALSE;
		}

		if (size < maximum_node_types)
		{
			idents[size] = ident;
			names[size] = name;

			++size;

			METRIC_NODE_TYPE_ADD(ident, name);

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

		return UNKNOWN_NODE_TYPE;
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

	command const char* NodeType.current_to_string(void)
	{
		return call NodeType.to_string(current_type);
	}

	command void NodeType.init(uint8_t ident)
	{
		METRIC_NODE_CHANGE(UNKNOWN_NODE_TYPE, "<unknown>", ident, call NodeType.to_string(ident));

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

	command uint8_t NodeType.get(void)
	{
		return current_type;
	}

	command uint8_t NodeType.unknown_type(void)
	{
		return UNKNOWN_NODE_TYPE;
	}


	command am_addr_t NodeType.get_topology_node_id(void)
	{
#ifdef TOSSIM
		return sim_mote_tag(sim_node());
#else
		return TOS_NODE_ID;
#endif
	}

	command bool NodeType.is_node_sink(void)
	{
		return call NodeType.is_topology_node_id(SINK_NODE_ID);
	}

	command bool NodeType.is_topology_node_id(uint16_t topo_nid)
	{
		return call NodeType.get_topology_node_id() == topo_nid;
	}
}
