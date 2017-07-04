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

#define CHOOSE_RETRY_LIMIT 20

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, BOTTOM, BOTTOM, BOTTOM)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

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

	uses interface MetricLogging;

	uses interface NodeType;
	uses interface MessageType;
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
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

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

	unsigned int extra_to_send = 0;

	bool busy = FALSE;
	message_t packet;

	bool ctp_route = FALSE;
	am_addr_t fake_walk_parent = AM_BROADCAST_ADDR;

	SequenceNumber fake_sequence_number;

	int32_t min_source_distance = BOTTOM;

	uint32_t choose_retry_count = 0;

	uint32_t send_wait(void)
	{
		return 18U + (uint32_t)(24U * random_float());
	}

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(CHOOSE_CHANNEL, "Choose");
		call MessageType.register_pair(FAKE_CHANNEL, "Fake");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
			call RootControl.setRoot();
		}
		else
		{
			call NodeType.init(NormalNode);
		}

		sequence_number_init(&fake_sequence_number);

		call RadioControl.start();

		call EtxTimer.startPeriodic(200);
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			LOG_STDOUT_VERBOSE(EVENT_RADIO_ON, "radio on\n");

			call RoutingControl.start();

			call ObjectDetector.start_later(5 * 1000);
		}
		else
		{
			ERROR_OCCURRED(ERROR_RADIO_CONTROL_START_FAIL, "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		LOG_STDOUT_VERBOSE(EVENT_RADIO_OFF, "radio off\n");
	}

	event void ObjectDetector.detect()
	{
		// A sink node cannot become a source node
		if (call NodeType.get() != SinkNode)
		{
			call NodeType.set(SourceNode);

			min_source_distance = 0;

			call SourcePeriodModel.startPeriodic();

			call BroadcastBeaconTimer.startOneShot(send_wait());
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call SourcePeriodModel.stop();

			min_source_distance = BOTTOM;

			call NodeType.set(NormalNode);
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

		simdbg("stdout", "Starting selection of next fake node with etx %u\n", etx);

		for (i = 0; i != num_neighbours; ++i)
		{
			const am_addr_t neighbour_addr = call CtpInfo.getNeighborAddr(i);
			const uint16_t link_quality = call CtpInfo.getNeighborLinkQuality(i);
			const uint16_t route_quality = call CtpInfo.getNeighborRouteQuality(i);

			const uint16_t neighbour_etx = route_quality - link_quality;

			const uint16_t* neighbour_min_source_distance = call NeighboursMinSourceDistance.get(neighbour_addr);

			const int32_t nmsd = neighbour_min_source_distance == NULL ? BOTTOM : (int32_t)*neighbour_min_source_distance;

			am_addr_t parent;

			simdbg("stdout", "Considering %u with link=%u route=%u q=%u nmsd=%d ::\t",
				neighbour_addr, link_quality, route_quality, neighbour_etx, nmsd);

			// Don't want to select a node adjacent to a source node
			if (call Sources.contains_key(neighbour_addr))
			{
				simdbg_clear("stdout", "discarded as child of CTP route\n");
				continue;
			}

			// Don't want to select any node that was part of the CTP route
			status = call CtpInfo.getParent(&parent);
			if (status == SUCCESS && neighbour_addr == parent)
			{
				simdbg_clear("stdout", "discarded as parent of CTP route\n");
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

	void become_fake_source(void)
	{
		ChooseMessage message;
		message.at_end = TRUE;

		simdbg("stdout", "Became PFS\n\n");

		call Leds.led1On();

		call FakeSendTimer.startPeriodic(750);

		send_Choose_message(&message, AM_BROADCAST_ADDR);

		choose_retry_count = 0;
	}

	void become_normal(void)
	{
		simdbg("stdout", "Became Normal\n\n");

		call Leds.led1Off();

		call FakeSendTimer.stop();
	}

	bool is_fake_source(void)
	{
		return call FakeSendTimer.isRunning();
	}


	event void SourcePeriodModel.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		if (send_Normal_message(&message))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}

		simdbgverbose("stdout", "%s: Generated Normal seqno=%u at %u.\n",
			sim_time_string(), message.sequence_number, message.source_id);
	}

	event void BroadcastBeaconTimer.fired()
	{
		BeaconMessage message;

		message.neighbour_min_source_distance = min_source_distance;

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	event void FakeWalkTimer.fired()
	{
		if (choose_retry_count >= CHOOSE_RETRY_LIMIT)
		{
			become_fake_source();
		}
		else
		{
			am_addr_t target;

			ChooseMessage message;
			message.at_end = FALSE;

			target = fake_walk_target();

			send_Choose_message(&message, target);

			choose_retry_count += 1;

			call FakeWalkTimer.startOneShot(send_wait());
		}
	}

	uint16_t etx = 0;

	event void FakeSendTimer.fired()
	{
		FakeMessage message;

		message.sequence_number = sequence_number_next(&fake_sequence_number);
		message.source_id = TOS_NODE_ID;
		message.sender_min_source_distance = min_source_distance;

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

			if (!ctp_route)
			{
				if (rcvd->source_distance >= 2 && (rcvd->source_distance % 2) == 0)
				{
					call FakeWalkTimer.startOneShot(send_wait());
				}
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
		METRIC_RCV_CHOOSE(rcvd);

		simdbg("stdout", "Normal receive choose\n");

		if (rcvd->at_end)
		{
			// Received choose telling us to stop sending choose messages
			become_normal();
		}
		else if (is_fake_source())
		{
			// Send a choose ack message to stop neighbours forwarding choose messages

			ChooseMessage message;
			message.at_end = TRUE;

			send_Choose_message(&message, AM_BROADCAST_ADDR);

			become_normal();

			choose_retry_count = 0;
		}
		else
		{
			const am_addr_t target = fake_walk_target();

			fake_walk_parent = source_addr;

			// If there is no target become a fake sources
			if (target == AM_BROADCAST_ADDR)
			{
				become_fake_source();
			}
			// Otherwise keep sending the choose message 
			else
			{
				call Leds.led2On();

				call FakeWalkTimer.startOneShot(send_wait());
			}
		}
	}


	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;
		case SourceNode:
		case SinkNode: break;
	RECEIVE_MESSAGE_END(Choose)


	void Normal_snoop_Choose(const ChooseMessage* rcvd, am_addr_t source_addr)
	{
		if (rcvd->at_end)
		{
			become_normal();
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Snoop)
		case NormalNode: Normal_snoop_Choose(rcvd, source_addr); break;
		case SourceNode:
		case SinkNode: break;
	RECEIVE_MESSAGE_END(Choose)


	void Normal_receive_Fake(const FakeMessage* rcvd, am_addr_t source_addr)
	{
		FakeMessage forwarding_message = *rcvd;

		METRIC_RCV_FAKE(rcvd);

		if (fake_walk_parent != AM_BROADCAST_ADDR)
		{
			//simdbg("stdout", "Received fake message from %u forwarding to %u\n", source_addr, fake_walk_parent);

			send_Fake_message(&forwarding_message, fake_walk_parent);
		}
		else if (ctp_route)
		{
			/*am_addr_t ctp_parent;

			if (call CtpInfo.getParent(&ctp_parent) == SUCCESS)
			{
				send_Fake_message(&forwarding_message, ctp_parent);
			}*/
		}

		if (is_fake_source())
		{
			if (rcvd->sender_min_source_distance != BOTTOM && min_source_distance != BOTTOM &&
				rcvd->sender_min_source_distance > min_source_distance)
			{
				become_normal();
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

		METRIC_RCV_BEACON(rcvd);

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
}
