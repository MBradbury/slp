#include "Common.h"
#include "metrics/MetricLogging.h"

#include <Timer.h>
#include <TinyError.h>

enum {
	//* Using log2 samples to avoid a divide. Sending a packet every 1 second will allow
	//* allow about 5000 samples. A packet every half second allows for 2500 samples, and
	//* a packet every quarter second allows for 1250 samples. 
	
	// When to send a packet is based upon how many samples have been taken, not a 
	// predetermined amount of time. Rough estimates of time can be found using the 
	// conversion stated above. 
	LOG2SAMPLES = 7,
};

module ReadRssiC
{
	uses interface Boot;
	uses interface Leds;

	uses interface SplitControl as RadioControl;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface CC2420Config as Config;
	uses interface Read<uint16_t> as ReadRssi;
}

implementation
{
	uint8_t channel;

	uint32_t total;
	uint16_t smallest;
	uint16_t largest;
	uint16_t reads;

	uint16_t read_fails;

	event void Boot.booted()
	{
		LOG_STDOUT(EVENT_BOOTED, "booted\n");

		total = 0;
		smallest = UINT16_MAX;
		largest = 0;
		reads = 0;

		read_fails = 0;

		call RadioControl.start();
	}

	task void read_rssi()
	{
		if (call ReadRssi.read() != SUCCESS)
		{
			read_fails += 1;

			if (read_fails == (1 << LOG2SAMPLES))
			{
				ERROR_OCCURRED(ERROR_RSSI_READ_FAILURE, "Failed to read RSSI (1 << " STRINGIFY(LOG2SAMPLES) ") times\n");

				read_fails = 0;
			}

			post read_rssi();
		}
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			LOG_STDOUT(EVENT_RADIO_ON, "radio on\n");

			channel = call Config.getChannel();

			post read_rssi();
		}
		else
		{
			ERROR_OCCURRED(ERROR_RADIO_CONTROL_START_FAIL, "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		LOG_STDOUT(EVENT_RADIO_OFF, "radio off\n");
	}

	event void ReadRssi.readDone(error_t result, uint16_t val)
	{
		bool send_metric = FALSE;
		uint16_t rssi_average;
		uint16_t rssi_smallest, rssi_largest;
		uint16_t rssi_reads;

		if (result != SUCCESS)
		{
			read_fails += 1;

			if (read_fails == (1 << LOG2SAMPLES))
			{
				ERROR_OCCURRED(ERROR_RSSI_READ_FAILURE, "Failed to read RSSI (1 << " STRINGIFY(LOG2SAMPLES) ") times\n");

				read_fails = 0;
			}

			post read_rssi();

			return;
		}

		read_fails = 0;

		atomic
		{
			total += val;
			reads += 1;

			if (largest < val) {
				largest = val;
			}

			if (smallest > val) {
				smallest = val;
			}

			send_metric = (reads == (1 << LOG2SAMPLES));

			if (send_metric)
			{
				rssi_average = (total >> LOG2SAMPLES);
				rssi_smallest = smallest;
				rssi_largest = largest;
				rssi_reads = reads;

				total = 0;
				largest = 0;
				reads = 0;
			}
		}

		post read_rssi();

		if (send_metric)
		{
			METRIC_RSSI(rssi_average, rssi_smallest, rssi_largest, rssi_reads, channel);
		}
	}

	event void Config.syncDone(error_t error) {}
}
