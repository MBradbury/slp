#include "Constants.h"

configuration ObjectDetectorP
{
	provides interface ObjectDetector;
}
implementation
{
	components ObjectDetectorImplP as App;

	ObjectDetector = App;
}
