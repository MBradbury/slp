#ifndef SLP_MESSAGE_QUEUE_INFO_H
#define SLP_MESSAGE_QUEUE_INFO_H

typedef struct message_queue_info
{
	message_t msg;
	uint32_t time_added;
	uint8_t rtx_attempts;
	bool ack_requested;

} message_queue_info_t;

#endif // SLP_MESSAGE_QUEUE_INFO_H
