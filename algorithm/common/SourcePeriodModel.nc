
interface SourcePeriodModel
{
	command uint32_t get();
	command void startPeriodic();
	command void stop();

	event void fired();
}
