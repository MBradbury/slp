#ifndef SLP_MESSAGES_COLLISIONMESSAGE_H
#define SLP_MESSAGES_COLLISIONMESSAGE_H

typedef nx_struct CollisionMessage {
    nx_am_addr_t a;
    nx_uint16_t a_hop;
    nx_uint16_t a_slot;
    nx_am_addr_t b;
    nx_uint16_t b_hop;
    nx_uint16_t b_slot;
} CollisionMessage;

inline SequenceNumberWithBottom Collision_get_sequence_number(const CollisionMessage* msg) { return BOTTOM; }
inline int32_t Collision_get_source_id(const CollisionMessage* msg) { return BOTTOM; }

#endif /* SLP_MESSAGES_COLLISIONMESSAGE_H */
