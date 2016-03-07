#ifndef UTILS_H
#define UTILS_H

#define MAX_NEIGHBOURS 20

typedef nx_struct IDList {
    nx_uint16_t count;
    nx_uint16_t ids[MAX_NEIGHBOURS];
} IDList;

typedef nx_struct SlotDetails {
    nx_am_addr_t id;
    nx_uint16_t slot;
    nx_uint16_t hop;
    IDList neighbours;
} SlotDetails;

typedef nx_struct SlotList {
    nx_uint16_t count;
    SlotDetails slots[MAX_NEIGHBOURS];
} SlotList;

IDList IDList_new();
void IDList_add(IDList* list, uint16_t id);
void IDList_sort(IDList* list);
uint16_t IDList_indexOf(IDList* list, uint16_t el);
IDList IDList_minus_parent(IDList* list, uint16_t parent);
void IDList_clear(IDList* list);

uint16_t rank(IDList* list, uint16_t id);

SlotDetails SlotDetails_new(uint16_t id, uint16_t slot, uint16_t hop, IDList neighbours);
SlotList SlotList_new();
void SlotList_add(SlotList* list, uint16_t id, uint16_t slot, uint16_t hop, IDList neighbours);
void SlotList_add_details(SlotList* list, SlotDetails details);
uint16_t SlotList_indexOf(const SlotList* list, uint16_t id);
bool SlotList_contains_id(const SlotList* list, uint16_t id);
bool SlotList_collision(const SlotList* list);
SlotList SlotList_n_from_s(SlotList* list, uint16_t slot);
SlotList SlotList_n_from_sh(SlotList* list, uint16_t slot, uint16_t hop);
SlotDetails SlotList_min_h(SlotList* list);
void SlotList_clear(SlotList* list);
SlotList SlotList_minus_parent(SlotList* list, uint16_t parent);
IDList SlotList_to_ids(const SlotList* list);

IDList IDList_new()
{
    IDList list;
    list.count = 0;
    return list;
}

void IDList_add(IDList* list, uint16_t id)
{
    if(list->count >= MAX_NEIGHBOURS) return;
    if(IDList_indexOf(list, id) != UINT16_MAX) return;
    list->ids[list->count] = id;
    list->count = list->count + 1;
}

void IDList_sort(IDList* list)
{
    uint16_t i,j,a;
    for(i = 0; i < list->count; ++i)
    {
        for(j = i+1; j < list->count; j++)
        {
            if(list->ids[i] > list->ids[j])
            {
                a = list->ids[i];
                list->ids[i] = list->ids[j];
                list->ids[j] = a;
            }
        }
    }
}

uint16_t IDList_indexOf(IDList* list, uint16_t el)
{
    uint16_t i;
    for(i = 0; i<list->count; i++)
    {
        if(el == list->ids[i]) return i;
    }
    return UINT16_MAX;
}

IDList IDList_minus_parent(IDList* list, uint16_t parent)
{
    IDList newList;
    uint16_t i;
    for(i=0; i< list->count; i++)
    {
        if(list->ids[i] != parent)
        {
            IDList_add(&newList, list->ids[i]);
        }
    }
    return newList;
}

void IDList_clear(IDList* list)
{
    list->count = 0;
}

uint16_t rank(IDList* list, uint16_t id)
{
    uint16_t i;
    IDList_sort(list);
    i = IDList_indexOf(list, id);
    if(i == UINT16_MAX) return UINT16_MAX;
    else return i+1;
}


SlotDetails SlotDetails_new(uint16_t id, uint16_t slot, uint16_t hop, IDList neighbours)
{
    SlotDetails s;
    s.id = id;
    s.slot = slot;
    s.hop = hop;
    s.neighbours = neighbours;
    return s;
}

SlotList SlotList_new()
{
    SlotList list;
    list.count = 0;
    return list;
}

void SlotList_add(SlotList* list, uint16_t id, uint16_t slot, uint16_t hop, IDList neighbours)
{
    uint16_t i;
    if(list->count >= MAX_NEIGHBOURS) return;
    i = SlotList_indexOf(list, id);
    if(i == UINT16_MAX){
        i = list->count;
        list->count = list->count + 1;
    }
    list->slots[i] = SlotDetails_new(id, slot, hop, neighbours);
}


void SlotList_add_details(SlotList* list, SlotDetails details)
{
    uint16_t i;
    if(list->count >= MAX_NEIGHBOURS) return;
    i = SlotList_indexOf(list, details.id);
    if(i == UINT16_MAX){
        i = list->count;
        list->count = list->count + 1;
    }
    list->slots[i] = details;
}

uint16_t SlotList_indexOf(const SlotList* list, uint16_t id)
{
    uint16_t i;
    for(i = 0; i < list->count; i++)
    {
        if(list->slots[i].id == id) return i;
    }
    return UINT16_MAX;
}

bool SlotList_contains_id(const SlotList* list, uint16_t id)
{
    return SlotList_indexOf(list, id) != UINT16_MAX;
}


bool SlotList_collision(const SlotList* list)
{
    uint16_t i,j;
    if(list->count == 0) return FALSE; //Should return false anyway
    for (i = 0; i < list->count; i++) {
        for (j = i + 1; j < list->count; j++) {
            if (list->slots[i].slot == list->slots[j].slot) {
                return TRUE;
            }
        }
    }
    return FALSE;
}

SlotList SlotList_n_from_s(SlotList* list, uint16_t slot)
{
    uint16_t i;
    SlotList slots;

    for(i=0; i<list->count; i++)
    {
        if(list->slots[i].slot == slot)
        {
            SlotList_add_details(&slots, list->slots[i]);
        }
    }
    return slots;
}

SlotList SlotList_n_from_sh(SlotList* list, uint16_t slot, uint16_t hop)
{
    uint16_t i;
    SlotList slots;

    for(i=0; i<list->count; i++)
    {
        if((list->slots[i].slot == slot) && (list->slots[i].hop == hop))
        {
            SlotList_add_details(&slots, list->slots[i]);
        }
    }
    return slots;
}


SlotDetails SlotList_min_h(SlotList* list)
{
    uint16_t i;
    uint16_t mini=0;
    uint16_t minhop = UINT16_MAX;
    for(i=0; i<list->count; i++)
    {
        if(list->slots[i].hop < minhop)
        {
            minhop = list->slots[i].hop;
            mini = i;
        }
    }
    return list->slots[mini];
}

void SlotList_clear(SlotList* list)
{
    list->count = 0;
}

SlotList SlotList_minus_parent(SlotList* list, uint16_t parent)
{
    SlotList newList;
    uint16_t i;
    for(i=0; i< list->count; i++)
    {
        if(list->slots[i].id != parent)
        {
            SlotList_add_details(&newList, list->slots[i]);
        }
    }
    return newList;
}

IDList SlotList_to_ids(const SlotList* list)
{
    IDList newList;
    uint16_t i;
    for(i=0; i<list->count; i++)
    {
        IDList_add(&newList, list->slots[i].id);
    }
    return newList;
}

#endif /* UTILS_H */
