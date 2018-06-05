
#define BASE16_LENGTH(inlen) (((inlen) * 2) + 1)

module Base16C
{
    provides interface Encode;
}
implementation
{
    command bool Encode.encode(char* buf, uint8_t buf_len, const void* payload, uint8_t payload_len)
    {
        static const char* hex_str = "0123456789ABCDEF";

        const uint8_t* const payload_u8 = (const uint8_t*)payload;
        int16_t i;

        if (buf_len < BASE16_LENGTH(payload_len))
        {
            buf[0] = '\0';
            return FALSE;
        }

        /*if (!payload_u8)
        {
            buf[0] = '\0';
            return FALSE;
        }*/

        for (i = 0; i != payload_len; ++i)
        {
            buf[i * 2 + 0] = hex_str[(payload_u8[i] >> 4)       ];
            buf[i * 2 + 1] = hex_str[(payload_u8[i]     ) & 0x0F];
        }

        buf[payload_len * 2] = '\0';

        return TRUE;
    }
}
