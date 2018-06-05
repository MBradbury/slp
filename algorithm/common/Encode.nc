
interface Encode
{
    command bool encode(char* buf, uint8_t buf_len, const void* payload, uint8_t payload_len);
}
