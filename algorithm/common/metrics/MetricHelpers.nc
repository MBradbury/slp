
interface MetricHelpers
{
	command int8_t getRssi(const message_t* m);
	command int16_t getLqi(const message_t* m);

	command uint8_t getTxPower(const message_t* m);
}
