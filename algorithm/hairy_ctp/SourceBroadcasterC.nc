#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "FakeMessage.h"
#include "ChooseMessage.h"
#include "BeaconMessage.h"

#include <CtpDebugMsg.h>
#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance)

module SourceBroadcasterC
{
	provides interface CollectionDebug;

	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as BroadcastBeaconTimer;
	uses interface Timer<TMilli> as FakeWalkTimer;
	uses interface Timer<TMilli> as FakeSendTimer;
	uses interface Timer<TMilli> as EtxTimer;

	uses interface AMPacket;

	uses interface SplitControl as RadioControl;
	uses interface RootControl;
	uses interface StdControl as RoutingControl;

	uses interface Send as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;
	uses interface Intercept as NormalIntercept;

	uses interface AMSend as ChooseSend;
	uses interface Receive as ChooseReceive;
	uses interface Receive as ChooseSnoop;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;
	uses interface Receive as FakeSnoop;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;

	//uses interface CollectionPacket;
	uses interface CtpInfo;
	//uses interface CtpCongestion;

	uses interface Dictionary<am_addr_t, uint16_t> as Sources;

	uses interface Dictionary<am_addr_t, uint16_t> as NeighboursMinSourceDistance;
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string(void)
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case NormalNode:			return "NormalNode";
		default:					return "<unknown> ";
		}
	}

	// Produces a random float between 0 and 1
	float random_float(void)
	{
		// There appears to be problem with the 32 bit random number generator
		// in TinyOS that means it will not generate numbers in the full range
		// that a 32 bit integer can hold. So use the 16 bit value instead.
		// With the 16 bit integer we get better float values to compared to the
		// fake source probability.
		// Ref: https://github.com/tinyos/tinyos-main/issues/248
		const uint16_t rnd = call Random.rand16();

		return ((float)rnd) / UINT16_MAX;
	}

	// This function is to be used by the source node to get the
	// period it should use at the current time.
	// DO NOT use this for nodes other than the source!
	uint32_t get_source_period(void)
	{
		assert(type == SourceNode);
		return call SourcePeriodModel.get();
	}

	uint32_t extra_to_send = 0;

	bool busy = FALSE;
	message_t packet;

	bool ctp_route = FALSE;
	am_addr_t fake_walk_parent = AM_BROADCAST_ADDR;

	SequenceNumber fake_sequence_number;

	int32_t min_source_distance = BOTTOM;

	uint32_t send_wait(void)
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	event void Boot.booted()
	{
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			call RootControl.setRoot();
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		sequence_number_init(&fake_sequence_number);

		call RadioControl.start();

		call EtxTimer.startPeriodic(200);
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call RoutingControl.start();

			call ObjectDetector.start_later(5 * 1000);
		}
		else
		{
			simdbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			simdbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;
			min_source_distance = 0;

			call BroadcastNormalTimer.startOneShot(get_source_period());

			call BroadcastBeaconTimer.startOneShot(send_wait());
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			type = NormalNode;

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	am_addr_t fake_walk_target(void)
	{
		am_addr_t target = AM_BROADCAST_ADDR;

		const uint8_t num_neighbours = call CtpInfo.numNeighbors();
		uint8_t i = 0;

		uint16_t etx;
		error_t status;

		uint16_t max_neighbour_etx = UINT16_MAX;

		status = call CtpInfo.getEtx(&etx);
		if (status == SUCCESS)
		{
			max_neighbour_etx = etx;
		}

		simdbg("stdout", "Starting selection of next fake node with etx %u\n", etx);

		for (i = 0; i != num_neighbours; ++i)
		{
			const am_addr_t neighbour_addr = call CtpInfo.getNeighborAddr(i);
			const uint16_t link_quality = call CtpInfo.getNeighborLinkQuality(i);
			const uint16_t route_quality = call CtpInfo.getNeighborRouteQuality(i);

			const uint16_t neighbour_etx = route_quality - link_quality;

			const uint16_t* neighbour_min_source_distance = call NeighboursMinSourceDistance.get(neighbour_addr);

			am_addr_t parent;

			simdbg("stdout", "Considering %u with link=%u route=%u q=%u ::\t", neighbour_addr, link_quality, route_quality, neighbour_etx);

			// Don't want to select any node that was part of the CTP route
			if (call Sources.contains_key(neighbour_addr))
			{
				simdbg_clear("stdout", "discarded as child of CTP route\n");
				continue;
			}

			status = call CtpInfo.getParent(&parent);
			if (status == SUCCESS && call Sources.contains_key(parent))
			{
				simdbg_clear("stdout", "discarded as parent of CTP route\n");
				continue;
			}

			// Do not select the source
			if (status == SUCCESS && etx == 0)
			{
				simdbg_clear("stdout", "discarded as sink\n");
				continue;
			}

			if (link_quality == UINT16_MAX || route_quality == UINT16_MAX || neighbour_etx == 0)
			{
				simdbg_clear("stdout", "discarded as unknown neighbour quality\n");
				continue;
			}

			if (neighbour_min_source_distance != NULL && *neighbour_min_source_distance < min_source_distance)
			{
				simdbg_clear("stdout", "discarded as our min source distance is higher than the neighbours\n");
				continue;
			}

			if (neighbour_etx > etx && neighbour_etx < max_neighbour_etx)
			{
				simdbg_clear("stdout", "SELECTED\n");

				max_neighbour_etx = neighbour_etx;
				target = neighbour_addr;
			}
			else
			{
				simdbg_clear("stdout", "discarded as quality is too low\n");
			}
		}

		simdbg("stdout", "Chosen fake node %u\n\n", target);

		return target;
	}

	USE_MESSAGE_NO_TARGET(Normal);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);
	USE_MESSAGE(Beacon);

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		if (send_Normal_message(&message))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}

		simdbgverbose("stdout", "%s: Generated Normal seqno=%u at %u.\n",
			sim_time_string(), message.sequence_number, message.source_id);

		call BroadcastNormalTimer.startOneShot(get_source_period());
	}

	event void BroadcastBeaconTimer.fired()
	{
		BeaconMessage message;

		message.neighbour_min_source_distance = min_source_distance;

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	event void FakeWalkTimer.fired()
	{
		ChooseMessage message;

		am_addr_t target = fake_walk_target();

		send_Choose_message(&message, target);
	}

	uint16_t etx = 0;

	event void FakeSendTimer.fired()
	{
		FakeMessage message;

		message.sequence_number = sequence_number_next(&fake_sequence_number);
		message.source_id = TOS_NODE_ID;

		send_Fake_message(&message, fake_walk_parent);

		sequence_number_increment(&fake_sequence_number);
	}

	event void EtxTimer.fired()
	{
		call CtpInfo.getEtx(&etx);
	}


	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		min_source_distance = minbot(min_source_distance, rcvd->source_distance + 1);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Sink Received unseen Normal seqno=%u srcid=%u from %u.\n",
				sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: break;
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: break;
	RECEIVE_MESSAGE_END(Normal)



	void Normal_snoop_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		min_source_distance = minbot(min_source_distance, rcvd->source_distance + 1);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Normal Snooped unseen Normal data=%u seqno=%u srcid=%u from %u.\n",
				sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: break;
		case SinkNode: break;
		case NormalNode: Normal_snoop_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)



	bool Normal_intercept_Normal(NormalMessage* const rcvd, am_addr_t source_addr)
	{
		uint16_t* source_count = call Sources.get(rcvd->source_id);
		if (source_count == NULL)
		{
			call Sources.put(rcvd->source_id, 1);
		}

		min_source_distance = minbot(min_source_distance, rcvd->source_distance + 1);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Normal Intercepted unseen Normal seqno=%u srcid=%u from %u.\n",
				sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);

			rcvd->source_distance += 1;

			if (!ctp_route && rcvd->source_distance >= 2 && (rcvd->source_distance % 3) == 0)
			{
				call FakeWalkTimer.startOneShot(send_wait());
			}
		}

		ctp_route = TRUE;

		return TRUE;
	}

	INTERCEPT_MESSAGE_BEGIN(Normal, Intercept)
		case SourceNode: break;
		case SinkNode: break;
		case NormalNode: return Normal_intercept_Normal(rcvd, source_addr);
	INTERCEPT_MESSAGE_END(Normal)


	void Normal_receive_Choose(const ChooseMessage* rcvd, am_addr_t source_addr)
	{
		const am_addr_t target = fake_walk_target();

		simdbg("stdout", "Normal receive choose\n");

		fake_walk_parent = source_addr;

		// If there is no target become a fake sources
		if (target == AM_BROADCAST_ADDR)
		{
			simdbg("stdout", "Became PFS\n\n");

			call Leds.led0On();

			call FakeSendTimer.startPeriodic(500);
		}
		// Otherwise keep sending the choose message 
		else
		{
			call Leds.led1On();

			call FakeWalkTimer.startOneShot(send_wait());
		}
	}


	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;
		case SourceNode:
		case SinkNode: break;
	RECEIVE_MESSAGE_END(Choose)

	RECEIVE_MESSAGE_BEGIN(Choose, Snoop)
		case NormalNode:
		case SourceNode:
		case SinkNode: break;
	RECEIVE_MESSAGE_END(Choose)


	void Normal_receive_Fake(const FakeMessage* rcvd, am_addr_t source_addr)
	{
		FakeMessage forwarding_message = *rcvd;

		if (fake_walk_parent != AM_BROADCAST_ADDR)
		{
			simdbg("stdout", "Received fake message from %u forwarding to %u\n", source_addr, fake_walk_parent);

			send_Fake_message(&forwarding_message, fake_walk_parent);
		}
		else if (ctp_route)
		{
			am_addr_t ctp_parent;

			if (call CtpInfo.getParent(&ctp_parent) == SUCCESS)
			{
				send_Fake_message(&forwarding_message, ctp_parent);
			}
		}
	}


	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case SourceNode:
		case SinkNode: break;
	RECEIVE_MESSAGE_END(Fake)

	RECEIVE_MESSAGE_BEGIN(Fake, Snoop)
		case NormalNode:
		case SourceNode:
		case SinkNode: break;
	RECEIVE_MESSAGE_END(Fake)


	void x_receive_Beacon(const BeaconMessage* rcvd, am_addr_t source_addr)
	{
		uint16_t* neighbour_min_source_distance = call NeighboursMinSourceDistance.get(source_addr);

		if (rcvd->neighbour_min_source_distance == BOTTOM)
		{
			return;
		}

		if (neighbour_min_source_distance == NULL)
		{
			call NeighboursMinSourceDistance.put(source_addr, rcvd->neighbour_min_source_distance);
		}
		else if (rcvd->neighbour_min_source_distance < *neighbour_min_source_distance)
		{
			*neighbour_min_source_distance = rcvd->neighbour_min_source_distance;
		}

		if (min_source_distance == BOTTOM || rcvd->neighbour_min_source_distance + 1 < min_source_distance)
		{
			min_source_distance = rcvd->neighbour_min_source_distance + 1;

			call BroadcastBeaconTimer.startOneShot(send_wait());
		}
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)

	// The following is simply for metric gathering.
	// The CTP debug events are hooked into so we have correctly record when a message has been sent.

	command error_t CollectionDebug.logEvent(uint8_t event_type) {
		//simdbg("stdout", "logEvent %u\n", event_type);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventSimple(uint8_t event_type, uint16_t arg) {
		//simdbg("stdout", "logEventSimple %u %u\n", event_type, arg);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventDbg(uint8_t event_type, uint16_t arg1, uint16_t arg2, uint16_t arg3) {
		//simdbg("stdout", "logEventDbg %u %u %u %u\n", event_type, arg1, arg2, arg3);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventMsg(uint8_t event_type, uint16_t msg, am_addr_t origin, am_addr_t node) {
		//simdbg("stdout", "logEventMessage %u %u %u %u\n", event_type, msg, origin, node);

		if (event_type == NET_C_FE_SENDDONE_WAITACK || event_type == NET_C_FE_SENT_MSG || event_type == NET_C_FE_FWD_MSG)
		{
			// TODO: FIXME
			// Likely to be double counting Normal message broadcasts due to METRIC_BCAST in send_Normal_message
			METRIC_BCAST(Normal, "success", UNKNOWN_SEQNO);
		}

		return SUCCESS;
	}
	command error_t CollectionDebug.logEventRoute(uint8_t event_type, am_addr_t parent, uint8_t hopcount, uint16_t metric) {
		//simdbg("stdout", "logEventRoute %u %u %u %u\n", event_type, parent, hopcount, metric);

		if (event_type == NET_C_TREE_SENT_BEACON)
		{
			METRIC_BCAST(CTPBeacon, "success", UNKNOWN_SEQNO);
		}

		else if (event_type == NET_C_TREE_RCV_BEACON)
		{
			METRIC_RCV(CTPBeacon, parent, BOTTOM, UNKNOWN_SEQNO, BOTTOM);
		}

		return SUCCESS;
	}
}
