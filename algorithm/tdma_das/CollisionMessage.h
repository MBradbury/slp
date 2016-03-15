#ifndef SLP_MESSAGES_COLLISIONMESSAGE_H
#define SLP_MESSAGES_COLLISIONMESSAGE_H

#include "utils.h"

typedef nx_struct CollisionMessage {
    nx_am_addr_t source_id;
    //SlotList slots;
} CollisionMessage;

inline int64_t Collision_get_sequence_number(const CollisionMessage* msg) { return BOTTOM; }
inline int32_t Collision_get_source_id(const CollisionMessage* msg) { return msg->source_id; }


#endif /* SLP_MESSAGES_COLLISIONMESSAGE_H */
