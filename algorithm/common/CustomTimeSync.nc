/*#include <message.h>*/

interface CustomTimeSync<SyncMessage>
{
    command error_t update(const SyncMessage* const message, uint16_t hops);
    command void init_message(SyncMessage* message, uint16_t hops);
}
