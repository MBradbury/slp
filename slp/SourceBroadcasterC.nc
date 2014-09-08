#include "AwayChooseMessage.h"
#include "Constants.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "SequenceNumber.h"

#include <Timer.h>
#include <TinyError.h>

#define max(a, b) \
	({ __typeof__(a) _a = (a); \
	   __typeof__(b) _b = (b); \
	   _a > _b ? _a : _b; })

#define min(a, b) \
	({ __typeof__(a) _a = (a); \
	   __typeof__(b) _b = (b); \
	   _a < _b ? _a : _b; })

#define minbot(a, b) \
	({ __typeof__(a) _a = (a); \
	   __typeof__(b) _b = (b); \
	   (_a == BOTTOM || _b < _a) ? _b : _a; })


#define DEBUG_PREFIX "%s: [%s] "
#define DEBUG_ARGS sim_time_string(), type_to_string()


#define mydbg(type, message, ...) dbg(type, DEBUG_PREFIX message, DEBUG_ARGS, ##__VA_ARGS__)
#define myerr(type, message, ...) dbgerror(type, DEBUG_PREFIX message, DEBUG_ARGS, ##__VA_ARGS__)


module SourceBroadcasterC
{
	uses
	{
		interface Boot;
		interface Leds;

		interface Timer<TMilli> as BroadcastNormalTimer;

		interface Packet;
		interface AMPacket;

		interface SplitControl as RadioControl;

		interface AMSend as NormalSend;
		interface Receive as NormalReceive;

		interface AMSend as AwaySend;
		interface Receive as AwayReceive;

		interface AMSend as ChooseSend;
		interface Receive as ChooseReceive;

		interface AMSend as FakeSend;
		interface Receive as FakeReceive;

		interface FakeMessageGenerator;
	}
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, PermFakeSourceNode, TempFakeSourceNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	typedef enum
	{
		UnknownAlgorithm, FurtherAlgorithm, GenericAlgorithm
	} AlgorithmType;

	AlgorithmType algorithm = UnknownAlgorithm;

	SequenceNumber normal_sequence_counter;
	SequenceNumber fake_sequence_counter;
	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;

	/// NORMAL/FAKE and SINK and SOURCE variables

	int32_t sink_source_distance = BOTTOM;

	/// NORMAL/FAKE VARIABLES
	
	int32_t source_distance = BOTTOM;
	int32_t sink_distance = BOTTOM;
	
	int32_t first_hop = BOTTOM;
	
	bool is_perm_fs_candidate = FALSE;
	
	bool seen_perm_fs = FALSE;
	
	/// SINK VARIABLES
	
	bool sink_sent_away_msg = FALSE;


	// Network variables

	bool busy = FALSE;
	message_t packet;

	// Implementation

	void setLeds(uint32_t val)
	{
		if (val & 0x01)
		  call Leds.led0On();
		else 
		  call Leds.led0Off();

		if (val & 0x02)
		  call Leds.led1On();
		else
		  call Leds.led1Off();

		if (val & 0x04)
		  call Leds.led2On();
		else
		  call Leds.led2Off();
	}

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case PermFakeSourceNode:	return "PermFS    ";
		case TempFakeSourceNode:	return "TempFS    ";
		case NormalNode:			return "NormalNode";
		default:					return "<unknown> ";
		}
	}

	//
	// Algorithm specialisations
	//

	bool should_forward_normal()
	{
		return sink_source_distance == BOTTOM ||
			   source_distance == BOTTOM ||
			   (sink_source_distance * 1.125) >= source_distance;
	}

	bool should_ignore_choose()
	{
		switch (algorithm)
		{
		case FurtherAlgorithm:
			return sink_source_distance != BOTTOM &&
				source_distance <= ((1.0 * sink_source_distance) / 2.0) - 1;

		case GenericAlgorithm:
			return sink_source_distance != BOTTOM &&
				source_distance <= ((3.0 * sink_source_distance) / 4.0);

		default:
			return FALSE;
		}
	}

	uint32_t get_perm_fs_period()
	{
		switch (algorithm)
		{
		case FurtherAlgorithm:
			return (uint32_t)(SOURCE_PERIOD_MS * 0.55);

		case GenericAlgorithm:
		default:
			return (uint32_t)(SOURCE_PERIOD_MS * 0.85);
		}
	}

	uint32_t get_temp_fake_messages_to_send()
	{
		const uint32_t d_source = source_distance == BOTTOM ? 0 : source_distance;
		const uint32_t d_sink_source = sink_source_distance == BOTTOM ? 0 : sink_source_distance;

		switch (algorithm)
		{
		case FurtherAlgorithm:
			return max(d_source, 1);

		case GenericAlgorithm:
		default:
			return max(d_source - d_sink_source, 1);
		}
	}


	//
	// Events
	//


	event void Boot.booted()
	{
		dbg("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);

		if (TOS_NODE_ID == 1)
		{
			type = SourceNode;
		}
		if (TOS_NODE_ID == 9)
		{
			type = SinkNode;
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			mydbg("SourceBroadcasterC", "RadioControl started.\n");

			// TODO: replace this with some other way to identify the source node
			if (type == SourceNode)
			{
				call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);
			}
		}
		else
		{
			myerr("SourceBroadcasterC", "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		mydbg("SourceBroadcasterC", "RadioControl stopped.\n");
	}

	bool generate_normal_message()
	{
		error_t status;

		if (!busy)
		{
			NormalMessage* const message = (NormalMessage*)(call Packet.getPayload(&packet, sizeof(NormalMessage)));
			if (message == NULL)
			{
				myerr("SourceBroadcasterC", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			message->sequence_number = sequence_number_next(&normal_sequence_counter);
			message->sink_source_distance = sink_source_distance;
			message->hop = 0;
			message->max_hop = first_hop;
			message->source_id = TOS_NODE_ID;

			status = call NormalSend.send(AM_BROADCAST_ADDR, &packet, sizeof(NormalMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;

				sequence_number_increment(&normal_sequence_counter);
			}

			return status == SUCCESS;
		}
		else
		{
			mydbg("SourceBroadcasterC", "BroadcastNormalTimer busy, not sending Normal message.\n");
			return FALSE;
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		mydbg("SourceBroadcasterC", "BroadcastNormalTimer fired.\n");

		generate_normal_message();
	}

	event void NormalSend.sendDone(message_t* msg, error_t error)
	{
		mydbg("SourceBroadcasterC", "NormalSend sendDone with status %i.\n", error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}

	event void AwaySend.sendDone(message_t* msg, error_t error)
	{
		mydbg("SourceBroadcasterC", "AwaySend sendDone with status %i.\n", error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}

	event void ChooseSend.sendDone(message_t* msg, error_t error)
	{
		mydbg("SourceBroadcasterC", "ChooseSend sendDone with status %i.\n", error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}

	event void FakeSend.sendDone(message_t* msg, error_t error)
	{
		mydbg("SourceBroadcasterC", "FakeSend sendDone with status %i.\n", error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}

	//
	// Fake sources
	//

	bool decide_if_temp_fake_source()
	{
		// TODO: probability
		return TRUE;
	}

	bool decide_if_perm_fake_source()
	{
		// TODO: probability
		return TRUE;
	}

	void possibly_become_temp_fake_source(const AwayChooseMessage* message)
	{
		if (decide_if_temp_fake_source())
		{
			type = TempFakeSourceNode;

			call FakeMessageGenerator.startLimited(message, FAKE_PERIOD_MS, get_temp_fake_messages_to_send());
		}

	}

	void possibly_become_perm_fake_source(const AwayChooseMessage* message)
	{
		if (decide_if_perm_fake_source())
		{
			type = PermFakeSourceNode;

			call FakeMessageGenerator.start(message, FAKE_PERIOD_MS);
		}
	}


	//
	// NORMAL processing
	//

	bool forward_normal_message(const NormalMessage* normal_rcvd)
	{
		error_t status;

		if (!busy)
		{
			NormalMessage* forwarding_message = (NormalMessage*)(call Packet.getPayload(&packet, sizeof(NormalMessage)));
			if (forwarding_message == NULL)
			{
				myerr("SourceBroadcasterC", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			*forwarding_message = *normal_rcvd;
			forwarding_message->hop += 1;
			forwarding_message->max_hop = max(first_hop, (uint32_t)forwarding_message->max_hop);

			status = call NormalSend.send(AM_BROADCAST_ADDR, &packet, sizeof(NormalMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;
			}

			return TRUE;
		}
		else
		{
			myerr("SourceBroadcasterC", "BroadcastNormal busy, not forwarding Normal message.\n");
			return FALSE;
		}
	}

	bool generate_away_message(const NormalMessage* normal_rcvd)
	{
		error_t status;

		if (!busy)
		{
			AwayMessage* message = (AwayMessage*)(call Packet.getPayload(&packet, sizeof(AwayMessage)));
			if (message == NULL)
			{
				myerr("SourceBroadcasterC", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			message->sequence_number = sequence_number_next(&away_sequence_counter);
			message->sink_source_distance = sink_source_distance;
			message->sink_distance = 0;
			message->max_hop = normal_rcvd->max_hop;
			message->source_id = TOS_NODE_ID;

			status = call AwaySend.send(AM_BROADCAST_ADDR, &packet, sizeof(AwayMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;

				sequence_number_increment(&away_sequence_counter);
			}

			return status == SUCCESS;
		}
		else
		{
			myerr("SourceBroadcasterC", "BroadcastAway busy, not sending Away message.\n");
			return FALSE;
		}
	}

	void sink_receive_normal(const NormalMessage* normal_rcvd, am_addr_t immediate_source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, (int32_t)normal_rcvd->sink_source_distance);

		if (sequence_number_before(&normal_sequence_counter, normal_rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, normal_rcvd->sequence_number);

			mydbg("SourceBroadcasterC", "Received unseen Normal seqno=%u from %u.\n", normal_rcvd->sequence_number, immediate_source_addr);

			if (!sink_sent_away_msg)
			{
				sink_sent_away_msg = TRUE;

				generate_away_message(normal_rcvd);
			}
		}
	}

	void normal_receive_normal(const NormalMessage* normal_rcvd, am_addr_t immediate_source_addr)
	{
		if (first_hop == BOTTOM || normal_rcvd->max_hop - 1 > first_hop)
		{
			is_perm_fs_candidate = FALSE;
		}

		sink_source_distance = minbot(sink_source_distance, (int32_t)normal_rcvd->sink_source_distance);
		source_distance = minbot(source_distance, (int32_t)normal_rcvd->hop + 1);

		if (sequence_number_before(&normal_sequence_counter, normal_rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, normal_rcvd->sequence_number);

			mydbg("SourceBroadcasterC", "Received unseen Normal seqno=%u from %u.\n", normal_rcvd->sequence_number, immediate_source_addr);

			// If this is the first time a Normal message has been
			// received by this node.
			if (first_hop == BOTTOM)
			{
				first_hop = normal_rcvd->hop + 1;

				is_perm_fs_candidate = TRUE;
			}

			if (should_forward_normal())
				forward_normal_message(normal_rcvd);
		}
		/*else
		{
			mydbg("SourceBroadcasterC", "Received previously seen Normal seqno=%u.\n", normal_msg->sequence_number);
		}*/
	}

	void fake_receive_normal(const NormalMessage* normal_rcvd, am_addr_t immediate_source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, (int32_t)normal_rcvd->sink_source_distance);
		source_distance = minbot(source_distance, (int32_t)normal_rcvd->hop + 1);

		if (sequence_number_before(&normal_sequence_counter, normal_rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, normal_rcvd->sequence_number);

			mydbg("SourceBroadcasterC", "Received unseen Normal seqno=%u from %u.\n", normal_rcvd->sequence_number, immediate_source_addr);

			if (should_forward_normal())
				forward_normal_message(normal_rcvd);
		}
		/*else
		{
			mydbg("SourceBroadcasterC", "Received previously seen Normal seqno=%u.\n", normal_msg->sequence_number);
		}*/
	}

	event message_t* NormalReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		const NormalMessage* const normal_rcvd = (const NormalMessage*)payload;
		am_addr_t immediate_source_addr;

		if (len != sizeof(NormalMessage))
		{
			myerr("SourceBroadcasterC", "Received Normal of invalid length %hhu.\n", len);
			return msg;
		}

		mydbg("SourceBroadcasterC", "Received valid Normal.\n");

		immediate_source_addr = call AMPacket.source(msg);

		setLeds(normal_rcvd->sequence_number);

		switch (type)
		{
		case SinkNode:
			sink_receive_normal(normal_rcvd, immediate_source_addr);
			break;

		case NormalNode:
			normal_receive_normal(normal_rcvd, immediate_source_addr);
			break;

		case TempFakeSourceNode:
		case PermFakeSourceNode:
			fake_receive_normal(normal_rcvd, immediate_source_addr);
			break;

		default:
			break;
		}

		return msg;
	}


	//
	// AWAY processing
	//


	bool forward_away_message(const AwayMessage* away_rcvd)
	{
		error_t status;

		if (!busy)
		{
			AwayMessage* forwarding_message = (AwayMessage*)(call Packet.getPayload(&packet, sizeof(AwayMessage)));
			if (forwarding_message == NULL)
			{
				myerr("SourceBroadcasterC", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			*forwarding_message = *away_rcvd;
			forwarding_message->sink_distance += 1;

			status = call AwaySend.send(AM_BROADCAST_ADDR, &packet, sizeof(AwayMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;
			}

			return TRUE;
		}
		else
		{
			myerr("SourceBroadcasterC", "BroadcastAway busy, not forwarding Away message.\n");
			return FALSE;
		}
	}


	void normal_receive_away(const AwayMessage* away_rcvd, am_addr_t immediate_source_addr)
	{
		if (first_hop == BOTTOM || away_rcvd->max_hop - 1 > first_hop)
		{
			is_perm_fs_candidate = TRUE;
		}

		sink_source_distance = minbot(sink_source_distance, (int32_t)away_rcvd->sink_source_distance);
		sink_distance = minbot(sink_distance, (int32_t)away_rcvd->sink_distance + 1);

		if (sequence_number_before(&away_sequence_counter, away_rcvd->sequence_number))
		{
			sequence_number_update(&away_sequence_counter, away_rcvd->sequence_number);

			// A sink distance of 0 indicates that this message was
			// just sent by the sink
			if (away_rcvd->sink_distance == 0)
			{
				possibly_become_temp_fake_source(away_rcvd);

				sequence_number_increment(&choose_sequence_counter);
			}

			// Keep sending away message throughout network
			forward_away_message(away_rcvd);
		}
	}

	void source_receive_away(const AwayMessage* away_rcvd, am_addr_t immediate_source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, (int32_t)away_rcvd->sink_source_distance);
		sink_distance = minbot(sink_distance, (int32_t)away_rcvd->sink_distance + 1);

		if (sequence_number_before(&away_sequence_counter, away_rcvd->sequence_number))
		{
			sequence_number_update(&away_sequence_counter, away_rcvd->sequence_number);

			// Keep sending away message throughout network
			forward_away_message(away_rcvd);
		}
	}

	event message_t* AwayReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		const AwayMessage* const away_rcvd = (const AwayMessage*)payload;
		am_addr_t immediate_source_addr;

		if (len != sizeof(AwayMessage))
		{
			myerr("SourceBroadcasterC", "Received Away of invalid length %hhu.\n", len);
			return msg;
		}

		mydbg("SourceBroadcasterC", "Received valid Away.\n");

		immediate_source_addr = call AMPacket.source(msg);

		setLeds(away_rcvd->sequence_number);

		switch (type)
		{
		case NormalNode:
			normal_receive_away(away_rcvd, immediate_source_addr);
			break;

		case SourceNode:
			source_receive_away(away_rcvd, immediate_source_addr);
			break;

		default:
			break;
		}

		return msg;
	}



	//
	// CHOOSE processing
	//

	event message_t* ChooseReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		const ChooseMessage* const choose_rcvd = (const ChooseMessage*)payload;
		am_addr_t immediate_source_addr;
		bool should_become_fake;

		if (len != sizeof(ChooseMessage))
		{
			myerr("SourceBroadcasterC", "Received Choose of invalid length %hhu.\n", len);
			return msg;
		}

		mydbg("SourceBroadcasterC", "Received valid Choose.\n");

		immediate_source_addr = call AMPacket.source(msg);

		setLeds(choose_rcvd->sequence_number);

		switch (type)
		{
		case NormalNode:

			if (first_hop == BOTTOM || choose_rcvd->max_hop -1 > first_hop)
			{
				is_perm_fs_candidate = FALSE;
			}

			// TODO: message algorithm

			sink_source_distance = minbot(sink_source_distance, (int32_t)choose_rcvd->sink_source_distance);

			should_become_fake = ! should_ignore_choose() &&
				sequence_number_before(&choose_sequence_counter, choose_rcvd->sequence_number);

			if (should_become_fake)
			{
				sequence_number_update(&choose_sequence_counter, choose_rcvd->sequence_number);

				if (is_perm_fs_candidate)
				{
					possibly_become_perm_fake_source(choose_rcvd);
				}
				else
				{
					possibly_become_temp_fake_source(choose_rcvd);
				}
			}

			break;

		default:
			break;
		}

		return msg;
	}




	//
	// FAKE processing
	//

	bool forward_fake_message(const FakeMessage* original_message)
	{
		error_t status;

		if (!busy)
		{
			FakeMessage* message = (FakeMessage*)(call Packet.getPayload(&packet, sizeof(FakeMessage)));
			if (message == NULL)
			{
				myerr("SourceBroadcasterC", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			*message = *original_message;
			message->sink_source_distance = sink_source_distance;
			message->travel_dist -= 1;

			status = call FakeSend.send(AM_BROADCAST_ADDR, &packet, sizeof(FakeMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;
			}

			return status == SUCCESS;
		}
		else
		{
			myerr("SourceBroadcasterC", "BroadcastAway busy, not sending Away message.\n");
			return FALSE;
		}
	}

	event message_t* FakeReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		const FakeMessage* const fake_rcvd = (const FakeMessage*)payload;
		am_addr_t immediate_source_addr;

		if (len != sizeof(FakeMessage))
		{
			myerr("SourceBroadcasterC", "Received Fake of invalid length %hhu.\n", len);
			return msg;
		}

		mydbg("SourceBroadcasterC", "Received valid Fake.\n");

		immediate_source_addr = call AMPacket.source(msg);

		setLeds(fake_rcvd->sequence_number);

		switch (type)
		{
		case NormalNode:
		case TempFakeSourceNode:
		case PermFakeSourceNode:

			if (first_hop == BOTTOM || fake_rcvd->max_hop -1 > first_hop)
			{
				is_perm_fs_candidate = FALSE;
			}

			sink_source_distance = minbot(sink_source_distance, (int32_t)fake_rcvd->sink_source_distance);

			seen_perm_fs |= fake_rcvd->from_permanent_fs;

			if (sequence_number_before(&fake_sequence_counter, fake_rcvd->sequence_number))
			{
				sequence_number_update(&fake_sequence_counter, fake_rcvd->sequence_number);

				if (fake_rcvd->travel_dist != 0)
				{
					forward_fake_message(fake_rcvd);
				}
			}

			// Revert to normal node when a perm fake source
			// is detected and is further from the source than this node is
			if (algorithm == GenericAlgorithm && type == PermFakeSourceNode)
			{
				if (fake_rcvd->from_permanent_fs &&
						(
						fake_rcvd->source_distance > source_distance ||
						(fake_rcvd->source_distance == source_distance && sink_distance < fake_rcvd->from_sink_distance) ||
						(fake_rcvd->source_distance == source_distance && sink_distance == fake_rcvd->from_sink_distance && TOS_NODE_ID < fake_rcvd->source_id)
						)
					)
				{
					type = NormalNode;
					call FakeMessageGenerator.stop();
				}
			}

			break;

		case SinkNode:
			sink_source_distance = minbot(sink_source_distance, (int32_t)fake_rcvd->sink_source_distance);

			seen_perm_fs |= fake_rcvd->from_permanent_fs;

			if (sequence_number_before(&fake_sequence_counter, fake_rcvd->sequence_number))
			{
				sequence_number_update(&fake_sequence_counter, fake_rcvd->sequence_number);

				if (fake_rcvd->travel_dist != 0)
				{
					forward_fake_message(fake_rcvd);
				}
			}

			break;

		case SourceNode:
			sink_source_distance = minbot(sink_source_distance, (int32_t)fake_rcvd->sink_source_distance);
			break;

		default:
			break;
		}

		return msg;
	}


	//
	// Fake Generator
	//

	bool generate_choose_message(const AwayChooseMessage* original_message)
	{
		error_t status;

		if (!busy)
		{
			ChooseMessage* message = (ChooseMessage*)(call Packet.getPayload(&packet, sizeof(ChooseMessage)));
			if (message == NULL)
			{
				myerr("SourceBroadcasterC", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			message->sequence_number = sequence_number_next(&choose_sequence_counter);
			message->sink_source_distance = original_message->sink_source_distance;
			message->sink_distance = original_message->sink_distance + 1;
			message->max_hop = first_hop;
			message->source_id = TOS_NODE_ID;

			status = call ChooseSend.send(AM_BROADCAST_ADDR, &packet, sizeof(ChooseMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;

				sequence_number_increment(&choose_sequence_counter);
			}

			return status == SUCCESS;
		}
		else
		{
			myerr("SourceBroadcasterC", "BroadcastAway busy, not sending Away message.\n");
			return FALSE;
		}
	}

	event void FakeMessageGenerator.generateFakeMessage(FakeMessage* message)
	{
		const double modifier = 1; //TODO

		message->sequence_number = sequence_number_next(&fake_sequence_counter);
		message->sink_source_distance = sink_source_distance;
		message->source_distance = source_distance;
		message->max_hop = first_hop;
		message->travel_dist = (uint32_t)ceil(modifier * source_distance);
		message->from_sink_distance = sink_distance;
		message->from_permanent_fs = (type == PermFakeSourceNode);
		message->source_id = TOS_NODE_ID;

		sequence_number_increment(&fake_sequence_counter);
	}

	event void FakeMessageGenerator.sendDone(const AwayChooseMessage* original_message)
	{
		mydbg("SourceBroadcasterC", "Finished sending Fake.\n");

		// When finished sending fake messages

		generate_choose_message(original_message);

		type = NormalNode;
	}

	event void FakeMessageGenerator.sent(error_t error)
	{
		mydbg("SourceBroadcasterC", "Sent Fake with error=%u.\n", error);
	}
}
