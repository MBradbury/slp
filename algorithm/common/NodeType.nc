
interface NodeType
{
	command bool register_pair(uint8_t ident, const char* name);

	command uint8_t from_string(const char* name);
	command const char* to_string(uint8_t ident);
	command const char* current_to_string(void);

	command void init(uint8_t ident);
	command void set(uint8_t ident);
	command uint8_t get(void);

	command uint8_t unknown_type(void);

	command am_addr_t get_topology_node_id(void);
	command bool is_topology_node_id(uint16_t topo_nid);
	command bool is_node_sink(void);
}
