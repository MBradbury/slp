
interface TDMA
{
	command void set_slot(uint16_t new_slot);
    command void set_valid_slot(uint16_t new_slot);
	command uint16_t get_slot();

	command bool is_slot_active();

	command void start();

	event void slot_changed(uint16_t old_slot, uint16_t new_slot);

	event bool dissem_fired();

	event void slot_started();
	event void slot_finished();
}
