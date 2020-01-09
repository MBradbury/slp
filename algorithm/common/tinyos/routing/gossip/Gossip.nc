
interface Gossip<Message>
{
	command error_t receive(Message* msg);

	event void send_message(const Message* msg);
}
