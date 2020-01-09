
interface ObjectDetector
{
	command void start();
	command void start_later(uint32_t delay);
	command void stop();
	
	event void detect();
	event void stoppedDetecting();

	command bool isDetected();
}
