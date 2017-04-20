
interface FaultModel
{
    command bool register_pair(uint8_t ident, const char* name);

    command uint8_t from_string(const char* name);
    command const char* to_string(uint8_t ident);

    command void fault_point(uint8_t ident);
}

