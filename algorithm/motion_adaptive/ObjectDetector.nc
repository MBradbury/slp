
interface ObjectDetector
{
	command void start();
	command void stop();
	
	event void detect();
	event void stoppedDetecting();

	command bool isDetected();
}
