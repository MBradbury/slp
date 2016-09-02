#include <stdint.h>

#ifndef DELAYED_BOOT_TIME_MIN
#define DELAYED_BOOT_TIME_MIN 6
#endif

module DelayedBootEventMainImplP
{
	provides interface Boot;

	uses interface Boot as OriginalBoot;
	uses interface Timer<TMilli> as DelayTimer;
}
implementation
{
	event void OriginalBoot.booted()
	{
#if defined(TOSSIM)
		signal Boot.booted();
#elif defined(TESTBED)
		call DelayTimer.startOneShot(DELAYED_BOOT_TIME_MIN * UINT32_C(60) * UINT32_C(1000));
#else
#	error "Unknown situation, should we delay the boot event or not?"
#endif
	}

	event void DelayTimer.fired()
	{
		signal Boot.booted();
	}
}
