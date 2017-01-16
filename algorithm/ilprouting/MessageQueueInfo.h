#ifndef SLP_MESSAGE_QUEUE_INFO_H
#define SLP_MESSAGE_QUEUE_INFO_H

typedef struct message_queue_info
{
	message_t msg;
	uint32_t time_added;
	am_addr_t proximate_source;
	uint8_t rtx_attempts;
	uint8_t calculate_target_attempts;
	bool ack_requested;

} message_queue_info_t;

#endif // SLP_MESSAGE_QUEUE_INFO_H
