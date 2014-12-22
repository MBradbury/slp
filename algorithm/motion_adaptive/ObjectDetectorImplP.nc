
module ObjectDetectorImplP
{
	provides interface ObjectDetector;
}
implementation
{
	bool detected = FALSE;

	command void ObjectDetector.start()
	{
		detected = (TOS_NODE_ID == SOURCE_NODE_ID);

		if (detected)
		{
			signal ObjectDetector.detect();
		}
	}

	command void ObjectDetector.stop()
	{
		detected = FALSE;
	}
	
	default event void ObjectDetector.detect()
	{
	}
	default event void ObjectDetector.stoppedDetecting()
	{
	}

	command bool ObjectDetector.isDetected()
	{
		return detected;
	}
}
