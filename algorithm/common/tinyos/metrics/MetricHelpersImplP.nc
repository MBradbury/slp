#include "MetricLogging.h"

module MetricHelpersImplP
{
	provides interface MetricHelpers;

#ifdef TOSSIM
	uses interface TossimPacket;
#else
	uses interface CC2420Packet;
#endif
}
implementation
{
	command int8_t MetricHelpers.getRssi(const message_t* m)
	{
#ifdef TOSSIM
		return call TossimPacket.strength((message_t*)m);
#else
		return call CC2420Packet.getRssi((message_t*)m);
#endif
	}

	command int16_t MetricHelpers.getLqi(const message_t* m)
	{
#ifdef TOSSIM
		// Tossim 2.1.2 doesn't have support for LQI
		// Head on github does
		return BOTTOM;
#else
		return call CC2420Packet.getLqi((message_t*)m);
#endif
	}

	command uint8_t MetricHelpers.getTxPower(const message_t* m)
	{
		uint8_t tx_power;
#ifdef TOSSIM
		// Tossim transmits at the max power which is level 31 (sort of...)
		tx_power = 31;
#else
		// For the CC2420 if the tx power for this message is
		// set to 0, then the default power level is used.
		tx_power = call CC2420Packet.getPower((message_t*)m);
		if (tx_power == 0)
		{
			tx_power = CC2420_DEF_RFPOWER;
		}
#endif

		return tx_power;
	}
}
