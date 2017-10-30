#include <stdint.h>

#ifndef DELAYED_BOOT_TIME_MINUTES
#define DELAYED_BOOT_TIME_MINUTES 10
#endif

module DelayedBootEventMainImplP
{
	provides interface Boot;

	uses interface Boot as OriginalBoot;

#if defined(TESTBED)
	uses interface Timer<TMilli> as DelayTimer;
#endif
}
implementation
{
	event void OriginalBoot.booted()
	{		
#if defined(TESTBED)
		call DelayTimer.startOneShot(DELAYED_BOOT_TIME_MINUTES * UINT32_C(60) * UINT32_C(1000));
#else
		signal Boot.booted();
#endif
	}

#if defined(TESTBED)
	event void DelayTimer.fired()
	{
		signal Boot.booted();
	}
#endif
}
