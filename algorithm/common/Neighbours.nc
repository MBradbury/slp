
interface Neighbours<Info, NBeaconMessage, NPollMessage>
{
	command error_t record(am_addr_t address, const Info* info);
	command error_t rtx_result(am_addr_t address, bool succeeded);

	command error_t pin(am_addr_t address);
	command error_t unpin(am_addr_t address);

	event void perform_update(Info* find, const Info* given);

	command uint16_t max_size();
	command uint16_t count();

	command Info* begin();
	command Info* end();

	command const am_addr_t* beginKeys();
	command const am_addr_t* endKeys();

	command Info* get_from_iter(const am_addr_t* iter);

	command void poll(const NPollMessage* data);
	command void fast_beacon();
	command void slow_beacon();

	event void generate_beacon(NBeaconMessage* message);

	event void rcv_poll(const NPollMessage* data, am_addr_t source);
	event void rcv_beacon(const NBeaconMessage* data, am_addr_t source);
}
