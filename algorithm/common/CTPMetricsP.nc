
#include "MetricLogging.h"

module CTPMetricsP
{
	provides interface CollectionDebug;
	uses interface CtpInfo;

	uses interface MetricLogging;
}

implementation
{
	// The following is simply for metric gathering.
	// The CTP debug events are hooked into so we have correctly record when a message has been sent.

	command error_t CollectionDebug.logEvent(uint8_t event_type) {
		//simdbg("stdout", "logEvent %u\n", event_type);

		switch (event_type)
		{
		case NET_C_FE_PUT_MSGPOOL_ERR:
			ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another message (NET_C_FE_PUT_MSGPOOL_ERR).\n");
			break;
		case NET_C_FE_PUT_QEPOOL_ERR:
			ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another message (NET_C_FE_PUT_QEPOOL_ERR).\n");
			break;
		case NET_C_FE_SEND_QUEUE_FULL:
			ERROR_OCCURRED(ERROR_QUEUE_FULL, "No queue space available for another message (NET_C_FE_SEND_QUEUE_FULL).\n");
			break;
		case NET_C_FE_MSG_POOL_EMPTY:
			ERROR_OCCURRED(ERROR_POOL_EMPTY, "The pool is empty (NET_C_FE_MSG_POOL_EMPTY).\n");
			break;
		case NET_C_FE_QENTRY_POOL_EMPTY:
			ERROR_OCCURRED(ERROR_POOL_EMPTY, "The pool is empty (NET_C_FE_QENTRY_POOL_EMPTY).\n");
			break;
		case NET_C_FE_SENDQUEUE_EMPTY:
			ERROR_OCCURRED(ERROR_QUEUE_EMPTY, "The queue is empty (NET_C_FE_SENDQUEUE_EMPTY).\n");
			break;
		}
		
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventSimple(uint8_t event_type, uint16_t arg) {
		//simdbg("stdout", "logEventSimple %u %u\n", event_type, arg);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventDbg(uint8_t event_type, uint16_t arg1, uint16_t arg2, uint16_t arg3) {
		//simdbg("stdout", "logEventDbg %u %u %u %u\n", event_type, arg1, arg2, arg3);

		if (event_type == NET_C_TREE_NEW_PARENT)
		{
			am_addr_t current_parent;
			const am_addr_t new_parent = arg1;

			error_t result = call CtpInfo.getParent(&current_parent);

			if (result == SUCCESS)
			{
				call MetricLogging.log_metric_parent_change(current_parent, new_parent);
			}
			else
			{
				call MetricLogging.log_metric_parent_change(AM_BROADCAST_ADDR, new_parent);
			}
		}

		return SUCCESS;
	}
	command error_t CollectionDebug.logEventMsg(uint8_t event_type, uint16_t msg, am_addr_t origin, am_addr_t node) {
		//simdbg("stdout", "logEventMessage %u %u %u %u\n", event_type, msg, origin, node);

		if (event_type == NET_C_FE_SENDDONE_WAITACK || event_type == NET_C_FE_SENT_MSG || event_type == NET_C_FE_FWD_MSG)
		{
			// TODO: FIXME
			// Likely to be double counting Normal message broadcasts due to METRIC_BCAST in send_Normal_message
			METRIC_BCAST(Normal, SUCCESS, UNKNOWN_SEQNO);
		}

		return SUCCESS;
	}
	command error_t CollectionDebug.logEventRoute(uint8_t event_type, am_addr_t parent, uint8_t hopcount, uint16_t metric) {
		//simdbg("stdout", "logEventRoute %u %u %u %u\n", event_type, parent, hopcount, metric);

		if (event_type == NET_C_TREE_SENT_BEACON)
		{
			METRIC_BCAST(CTPBeacon, SUCCESS, UNKNOWN_SEQNO);
		}

		else if (event_type == NET_C_TREE_RCV_BEACON)
		{
			METRIC_DELIVER(CTPBeacon, parent, BOTTOM, UNKNOWN_SEQNO);
			METRIC_RCV(CTPBeacon, parent, BOTTOM, UNKNOWN_SEQNO, BOTTOM);
		}

		return SUCCESS;
	}
}
