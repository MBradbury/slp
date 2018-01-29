
interface CustomTime
{
    command uint32_t local_time();
    command uint32_t global_time();

    command uint32_t local_to_global(uint32_t time);
    command uint32_t global_to_local(uint32_t time);
}
