#include "Constants.h"

generic configuration ReliableUnicastP(am_id_t AMId)
{
	provides
	{
		interface AMSend;
		interface Packet;
	    interface AMPacket;
	    interface PacketAcknowledgements as Acks;
	    interface PacketLink;
	}
}
implementation
{
	components ReliableUnicastImplP as App;

	AMSend = App;
	PacketLink = App;

	// Timers
	components new TimerMilliC() as DelayTimer;

	App.DelayTimer -> DelayTimer;

	components new AMSenderC(AMId) as Sender;

	App.Sender -> Sender;
	App.PacketAcknowledgements -> Sender;

	components new StateC() as SendState;

	App.SendState -> SendState;


	Packet = Sender;
	AMPacket = Sender;
	Acks = Sender;
}
