
#include "Gossip.h"

generic configuration GossipC(typedef Message, uint16_t MESSAGE_POOL_SIZE, uint32_t wait_period)
{
	provides interface Gossip<Message>;

	uses interface MetricLogging;
	uses interface MetricHelpers;
	uses interface Compare<Message>;
}
implementation
{
	components new GossipP(Message, wait_period);
	Gossip = GossipP;
	GossipP.MetricLogging = MetricLogging;

	components LocalTimeMilliC;
	GossipP.LocalTime -> LocalTimeMilliC;

	components new TimerMilliC() as WaitTimer;
    GossipP.WaitTimer -> WaitTimer;

    components new DictionaryC(Message, gossip_message_info_t, MESSAGE_POOL_SIZE) as MessageDict;
	GossipP.MessageDict -> MessageDict;

	components new CircularBufferC(Message, MESSAGE_POOL_SIZE) as SentCache;
	GossipP.SentCache -> SentCache;

	MessageDict.Compare = Compare;
	SentCache.Compare = Compare;
}
