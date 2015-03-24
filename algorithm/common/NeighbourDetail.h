#ifndef SLP_NEIGHBOURDETAIL_H
#define SLP_NEIGHBOURDETAIL_H

#define DEFINE_NEIGHBOUR_DETAIL(TYPE, TYPE_PREFIX, UPDATE_FN, PRINT_FN, MAX_SIZE) \
	typedef struct \
	{ \
		am_addr_t address; \
		TYPE contents; \
	} TYPE_PREFIX##_neighbour_detail_t; \
 \
	typedef struct \
	{ \
		TYPE_PREFIX##_neighbour_detail_t data[MAX_SIZE]; \
		uint32_t size; \
	} TYPE_PREFIX##_neighbours_t; \
 \
	void init_##TYPE_PREFIX##_neighbours(TYPE_PREFIX##_neighbours_t* neighbours) \
	{ \
		neighbours->size = 0; \
	} \
 \
	TYPE_PREFIX##_neighbour_detail_t* find_##TYPE_PREFIX##_neighbour(TYPE_PREFIX##_neighbours_t* neighbours, am_addr_t address) \
	{ \
		uint32_t i; \
		for (i = 0; i != neighbours->size; ++i) \
		{ \
			if (neighbours->data[i].address == address) \
			{ \
				return &neighbours->data[i]; \
			} \
		} \
		return NULL; \
	} \
 \
	bool insert_##TYPE_PREFIX##_neighbour(TYPE_PREFIX##_neighbours_t* neighbours, am_addr_t address, TYPE const* new_detail) \
	{ \
		TYPE_PREFIX##_neighbour_detail_t* find = find_##TYPE_PREFIX##_neighbour(neighbours, address); \
 \
		if (find != NULL) \
		{ \
			UPDATE_FN(&find->contents, new_detail); \
		} \
		else \
		{ \
			if (neighbours->size < MAX_SIZE) \
			{ \
				find = &neighbours->data[neighbours->size]; \
 \
				find->address = address; \
				memcpy(&find->contents, new_detail, sizeof(TYPE)); \
 \
				neighbours->size += 1; \
			} \
		} \
 \
		return find != NULL; \
	} \
 \
	void print_##TYPE_PREFIX##_neighbours(char* name, TYPE_PREFIX##_neighbours_t const* neighbours) \
	{ \
		uint32_t i; \
		dbg(name, "Neighbours(size=%d, values=", neighbours->size); \
		for (i = 0; i != neighbours->size; ++i) \
		{ \
			TYPE_PREFIX##_neighbour_detail_t const* neighbour = &neighbours->data[i]; \
			PRINT_FN(name, i, neighbour->address, &neighbour->contents); \
 \
			if ((i + 1) != neighbours->size) \
			{ \
				dbg_clear(name, ", "); \
			} \
		} \
		dbg_clear(name, ")\n"); \
	} \

#endif // SLP_NEIGHBOURDETAIL_H
