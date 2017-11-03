#ifndef SLP_MESSAGE_QUEUE_INFO_H
#define SLP_MESSAGE_QUEUE_INFO_H

#include <message.h>

#include "Constants.h"

typedef struct message_queue_info
{
	message_t msg;
	uint32_t time_added;
	am_addr_t proximate_source;
	uint8_t rtx_attempts;
	uint8_t calculate_target_attempts;
	bool ack_requested;

	// A list of neighbours we have failed to send to
	am_addr_t failed_neighbour_sends[RTX_ATTEMPTS];

} message_queue_info_t;

inline uint8_t failed_neighbour_sends_length(const message_queue_info_t* info)
{
	return RTX_ATTEMPTS - info->rtx_attempts;
}

#endif // SLP_MESSAGE_QUEUE_INFO_H
