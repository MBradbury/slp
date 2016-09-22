#ifndef SLP_SPANNING_TREE_H
#define SLP_SPANNING_TREE_H

enum {
	AM_SPANNING_TREE_SETUP = 15,
	AM_SPANNING_TREE_CONNECT = 16,
	AM_SPANNING_TREE_ROUTE = 17,
};

#define SLP_MAX_1_HOP_NEIGHBOURHOOD 12

#define SLP_SEND_QUEUE_SIZE 8

#define SLP_SPANNING_TREE_MAX_RETRIES 10

typedef nx_struct spanning_tree_data_header {

	nx_am_addr_t ultimate_source;
	nx_uint8_t seqno;
	nx_uint8_t sub_id;

} spanning_tree_data_header_t;

typedef struct {
	message_t* msg;
	bool ack_requested;
	uint8_t num_retries;
	
} send_queue_item_t;

#endif // SLP_SPANNING_TREE_H
