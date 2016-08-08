
interface NodeType
{
	command bool register_pair(uint8_t ident, const char* name);

	command uint8_t from_string(const char* name);
	command const char* to_string(uint8_t ident);
	command const char* current_to_string();

	command void init(uint8_t ident);
	command void set(uint8_t ident);
	command uint8_t get();
}
