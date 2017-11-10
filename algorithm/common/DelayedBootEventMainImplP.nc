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

	uses interface MetricLogging;
}
implementation
{
	void signal_boot()
	{
		METRIC_BOOT();
		signal Boot.booted();
	}

	event void OriginalBoot.booted()
	{		
#if defined(TESTBED)
		call DelayTimer.startOneShot(DELAYED_BOOT_TIME_MINUTES * UINT32_C(60) * UINT32_C(1000));
#else
		signal_boot();
#endif
	}

#if defined(TESTBED)
	event void DelayTimer.fired()
	{
		signal_boot();
	}
#endif
}
