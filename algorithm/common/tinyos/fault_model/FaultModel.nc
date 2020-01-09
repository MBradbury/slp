
interface FaultModel
{
    command bool register_pair(uint8_t ident, const char* name);

    command uint8_t from_string(const char* name);
    command const char* to_string(uint8_t ident);

    //command bool register_variable(uint8_t ident, const char* name, void* ptr, size_t data_size);

    command void fault_point(uint8_t ident);
}
