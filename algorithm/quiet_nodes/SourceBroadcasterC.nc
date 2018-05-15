#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->landmark_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

typedef struct
{
	int16_t distance;
} distance_container_t;

void distance_container_update(distance_container_t* find, distance_container_t const* given)
{
	find->distance = minbot(find->distance, given->distance);
}

void distance_container_print(const char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%zu] => addr=%u / dist=%d",
		i, address, contents->distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_container_update, distance_container_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(rcvd, source_addr, name) \
{ \
	const distance_container_t dist = {rcvd->name}; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_LANDMARK_DISTANCE(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		landmark_distance = minbot(landmark_distance, rcvd->name + 1); \
	} \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Crc;

	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Packet;
	uses interface AMPacket;
	
	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as AwaySeqNos;
	 
	uses interface Random;
}

implementation 
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	enum
	{
		SleepNode, OtherNode
	};


	int16_t landmark_distance = BOTTOM;
	int16_t source_distance = BOTTOM;
	int16_t sink_source_distance = BOTTOM;
	//int16_t sleep_timer = SLEEP_DURATION_FACTOR;

	distance_neighbours_t neighbours;

	bool busy = FALSE;
	int16_t nc = BOTTOM;
	bool sleep_status = FALSE;

	message_t packet;

	unsigned int extra_to_send = 0;

	// Produces a random float between 0 and 1
	float random_float()
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

	uint32_t beacon_send_wait()
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Beacon);

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		init_distance_neighbours(&neighbours);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
			//sink_distance = 0;
		}
		else
		{
			call NodeType.init(NormalNode);
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			LOG_STDOUT_VERBOSE(EVENT_RADIO_ON, "radio on\n");

			call ObjectDetector.start_later(1000);
			//call ObjectDetector.start();

			if (call NodeType.get() == SinkNode)
			{
				call AwaySenderTimer.startOneShot(1 * 1000); // One second
			}
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

			LOG_STDOUT(EVENT_OBJECT_DETECTED, "An object has been detected\n");

			call SourcePeriodModel.startPeriodic();
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			LOG_STDOUT(EVENT_OBJECT_STOP_DETECTED, "An object has stopped being detected\n");

			call SourcePeriodModel.stop();

			call NodeType.set(NormalNode);
		}
	}

	event void SourcePeriodModel.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.sink_source_distance = landmark_distance;

		//simdbg("stdout", "sink-source -distance is %d\n", landmark_distance);

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			simdbg("stdout", "normal message sent\n");
			call NormalSeqNos.increment(TOS_NODE_ID);
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		landmark_distance = 0;

		simdbgverbose("SourceBroadcasterC", "AwaySenderTimer fired.\n");

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = landmark_distance;

		call Packet.clear(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}

		simdbgverbose("stdout", "Away sent\n");
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		simdbgverbose("SourceBroadcasterC", "BeaconSenderTimer fired.\n");

		message.landmark_distance_of_sender = landmark_distance;

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const uint16_t rnd = call Random.rand16() % 100;
		int16_t become_sleep_p;
		int16_t sleep_timer;
		int16_t sleep_duration;

		//simdbg("stdout", "[%d]rnd = %d\n", TOS_NODE_ID, rnd);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			sink_source_distance = rcvd->sink_source_distance;

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;


			// Update the source-node distance
			if (source_distance == BOTTOM || source_distance > rcvd->source_distance + 1)
			{
				source_distance = rcvd->source_distance + 1;
			}

			// landmark_distance is 1 , p = 100. 
			become_sleep_p = 100 * (sink_source_distance - landmark_distance) / (sink_source_distance - 1);

			// landmark_distance = 1, duration is sink_source_distance; 
			// landmark_distance = 0.5 sink_source_distance, duration is 1.
			sleep_duration = (sink_source_distance-1)*landmark_distance/(1-0.5*sink_source_distance) + (1-0.5*sink_source_distance*sink_source_distance)/(1-0.5*sink_source_distance);

			sleep_timer = sleep_duration;

			// Update the nodes classification
			if (source_distance + landmark_distance <= sink_source_distance + 2 * QUIET_NODE_DISTANCE)
			{
				nc = SleepNode;
			}
			else
			{
				nc = OtherNode;
			}

			simdbg("stdout", "[%d] NC = %d. the source distance is %d, sink distance is %d, sink-source distance is %d\n", 
						TOS_NODE_ID, nc, source_distance, landmark_distance, sink_source_distance);

			if (sleep_status == FALSE)
			{
				switch (nc)
				{
					case SleepNode:
					{
						if ((forwarding_message.sequence_number == landmark_distance || forwarding_message.sequence_number +1 == landmark_distance) 
							&& rnd <= become_sleep_p && sleep_timer > 0)
						{
							sleep_status = TRUE;
							sleep_timer --;
							simdbg("stdout", "[Sequence:%d, ID: %d, P = %d], {Strong}I am sleep.\n", forwarding_message.sequence_number, TOS_NODE_ID, become_sleep_p);
						}
						else
							send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
						break;
					}
					case OtherNode:
					{
						if (forwarding_message.sequence_number == landmark_distance && rnd <= SLEEP_NODE_LOW_P && sleep_timer > 0)
						{
							sleep_status = TRUE;
							sleep_timer --;
							//simdbg("stdout", "[Sequence:%d, ID: %d], {Weak}I am sleep.\n", forwarding_message.sequence_number, TOS_NODE_ID);
						}
						else
							send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
						break;
					}
					default:
						send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
				}
			}
			// nodes in sleep mode
			else
			{
				//simdbg("stdout", "[Sequence:%d, Timer:%d, ID: %d], {Still}I am sleep.\n", forwarding_message.sequence_number, sleep_timer, TOS_NODE_ID);
				sleep_timer --;
				if (sleep_timer <= 0)
				{
					sleep_status = FALSE;
					sleep_timer = sleep_duration;
				}
			}
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	void Source_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: Normal_receive_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receive_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);
	}

	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		//simdbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dist=%d, my-dist=%d)\n",
		//  source_addr, call AMPacket.destination(msg), rcvd->landmark_distance_of_sender, landmark_distance);
	}

	// We need to snoop packets that may be unicasted,
	// so the attacker properly responds to them.
	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: x_snoop_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_snoop_Normal(msg, rcvd, source_addr); break;
		case NormalNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance);

		if (call AwaySeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			call AwaySeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.landmark_distance += 1;

			call Packet.clear(&packet);
			
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}

#ifdef SLP_VERBOSE_DEBUG
		print_distance_neighbours("stdout", &neighbours);
#endif
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receive_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
