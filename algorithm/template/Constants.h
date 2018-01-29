#ifndef SLP_CONSTANTS_H
#define SLP_CONSTANTS_H

enum Channel
{
	NORMAL_CHANNEL = 1,
	AWAY_CHANNEL = 2,
	CHOOSE_CHANNEL = 3,
	FAKE_CHANNEL = 4
};

enum NodeTypes
{
    SourceNode = 0,
    SinkNode = 1,
    NormalNode = 2,
    TempFakeNode = 3,
    PermFakeNode = 4,
};

#define SLP_OBJECT_DETECTOR_START_DELAY_MS (4 * 1000)

#endif // SLP_CONSTANTS_H
