
interface TDMAMultiSlot
{
    command uint8_t get_total_slots();
    command uint16_t get_slot(uint8_t num);
    command error_t set_slot(uint8_t num, uint16_t new_slot);
    command uint16_t get_current_slot();
    command uint16_t get_next_slot();

    command bool is_slot_active();
    command bool is_dissem_next();

    command void start();

    event void slot_changed(uint8_t num, uint16_t old_slot, uint16_t new_slot);

    event bool dissem_fired();

    event void slot_started(uint8_t num);
    event void slot_finished(uint8_t num);
}
