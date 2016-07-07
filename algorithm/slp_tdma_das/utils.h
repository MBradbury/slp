#ifndef UTILS_H
#define UTILS_H

#include "Constants.h"

#include <string.h>
#include <stdlib.h>

#include <assert.h>

#define MAX_ONEHOP SLP_MAX_1_HOP_NEIGHBOURHOOD
#define MAX_TWOHOP SLP_MAX_2_HOP_NEIGHBOURHOOD

typedef nx_struct IDList {
    nx_uint16_t count;
    nx_am_addr_t ids[MAX_TWOHOP];
} IDList;

typedef nx_struct NeighbourInfo {
    nx_am_addr_t id;
    nx_uint16_t hop;
    nx_uint16_t slot;
} NeighbourInfo;

typedef nx_struct NeighbourList {
    nx_uint16_t count;
    NeighbourInfo info[MAX_TWOHOP];
} NeighbourList;

typedef nx_struct OnehopList {
    nx_uint16_t count;
    NeighbourInfo info[MAX_ONEHOP];
} OnehopList;

typedef nx_struct OtherInfo {
    nx_am_addr_t id;
    IDList N;
} OtherInfo;

typedef nx_struct OtherList {
    nx_uint16_t count;
    OtherInfo info[MAX_TWOHOP];
} OtherList;




IDList IDList_new();
void IDList_add(IDList* list, am_addr_t id);
void IDList_sort(IDList* list);
uint16_t IDList_indexOf(IDList* list, am_addr_t el);
IDList IDList_minus_parent(IDList* list, am_addr_t parent);
void IDList_clear(IDList* list);
void IDList_print(const IDList* list);

uint16_t rank(IDList* list, am_addr_t id);

NeighbourInfo NeighbourInfo_new(am_addr_t id, uint16_t hop, uint16_t slot);
NeighbourList NeighbourList_new();
void NeighbourList_add(NeighbourList* list, am_addr_t id, uint16_t hop, uint16_t slot);
void NeighbourList_add_info(NeighbourList* list, const NeighbourInfo* info);
uint16_t NeighbourList_indexOf(const NeighbourList* list, am_addr_t id);
NeighbourInfo* NeighbourList_get(NeighbourList* list, am_addr_t id);
NeighbourInfo* NeighbourList_info_for_min_hop(NeighbourList* list, const IDList* parents);
void NeighbourList_select(NeighbourList* list, const IDList* onehop, OnehopList* newList);
void NeighbourList_to_OnehopList(const NeighbourList* list, OnehopList *newList);
void OnehopList_to_NeighbourList(const OnehopList* list, NeighbourList* newList);
uint16_t OnehopList_min_slot(OnehopList* list);

void NeighbourInfo_print(const NeighbourInfo* info);
void OnehopList_print(const OnehopList* list);
void NeighbourList_print(const NeighbourList* list);
uint16_t OnehopList_min_slot(OnehopList* list)
{
    uint16_t min_slot = list->info[0].slot;
    int i;
    for(i = 0; i < list->count; i++)
    {
        min_slot = (min_slot > list->info[i].slot) ? list->info[i].slot : min_slot;
    }
    return min_slot;
}

OtherInfo OtherInfo_new(am_addr_t id);
OtherList OtherList_new();
void OtherList_add(OtherList* list, OtherInfo info);
uint16_t OtherList_indexOf(const OtherList* list, am_addr_t id);
OtherInfo* OtherList_get(OtherList* list, am_addr_t id);


IDList IDList_new()
{
    IDList list;
    list.count = 0;
    return list;
}

void IDList_add(IDList* list, am_addr_t id)
{
    if(list->count >= MAX_TWOHOP)
    {
        simdbgerror("stdout", "IDList is full\n");
        return;
    }

    if(IDList_indexOf(list, id) != UINT16_MAX) return;
    list->ids[list->count] = id;
    list->count = list->count + 1;
}

int IDList_compare(const void* elem1, const void* elem2)
{
    const uint16_t id1 = *(const uint16_t*)elem1;
    const uint16_t id2 = *(const uint16_t*)elem2;
    if (id1 > id2) return +1;
    if (id1 < id2) return -1;
    return 0;
}

void IDList_sort(IDList* list)
{
    simdbg("stdout", "IDList before sort: "); IDList_print(list); simdbg_clear("stdout", "\n");
    qsort(list->ids, list->count, sizeof(list->ids[0]), &IDList_compare);
    simdbg("stdout", "IDList after sort: "); IDList_print(list); simdbg_clear("stdout", "\n");
}

uint16_t IDList_indexOf(IDList* list, am_addr_t el)
{
    uint16_t i;
    for(i = 0; i<list->count; i++)
    {
        if(el == list->ids[i]) return i;
    }
    return UINT16_MAX;
}

IDList IDList_minus_parent(IDList* list, am_addr_t parent)
{
    IDList newList = IDList_new();
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

void IDList_print(const IDList* list)
{
    uint16_t i;
    simdbg_clear("stdout", "IDList size=%u [", list->count);
    for (i = 0; i < list->count; ++i)
    {
        simdbg_clear("stdout", "%u, ", list->ids[i]);
    }
    simdbg_clear("stdout", "]");
}

uint16_t rank(IDList* list, am_addr_t id)
{
    uint16_t i;
    IDList_sort(list);
    i = IDList_indexOf(list, id);
    if(i == UINT16_MAX) return UINT16_MAX;
    else return i+1;
}




NeighbourInfo NeighbourInfo_new(am_addr_t id, uint16_t hop, uint16_t slot)
{
    NeighbourInfo info;
    info.id = id;
    info.hop  = hop;
    info.slot = slot;
    return info;
}

NeighbourList NeighbourList_new()
{
    NeighbourList list;
    list.count = 0;
    return list;
}

void NeighbourList_add(NeighbourList* list, am_addr_t id, uint16_t hop, uint16_t slot)
{
    const NeighbourInfo info = NeighbourInfo_new(id, hop, slot);
    NeighbourList_add_info(list, &info);
}

void NeighbourList_add_info(NeighbourList* list, const NeighbourInfo* info)
{
    uint16_t i;
    i = NeighbourList_indexOf(list, info->id);
    if(i == UINT16_MAX){
        if(list->count >= MAX_TWOHOP)
        {
            simdbgerror("stdout", "NeighbourList is full.\n");
            return;
        }
        i = list->count;
        list->count += 1;
    }
    list->info[i] = *info;
}

uint16_t NeighbourList_indexOf(const NeighbourList* list, am_addr_t id)
{
    uint16_t i;
    for(i = 0; i < list->count; i++)
    {
        if(list->info[i].id == id) return i;
    }
    return UINT16_MAX;
}

NeighbourInfo* NeighbourList_get(NeighbourList* list, am_addr_t id)
{
    int i;
    for(i=0; i<list->count; i++)
    {
        if(list->info[i].id == id)
        {
            return &(list->info[i]);
        }
    }
    return NULL;
}

NeighbourInfo* NeighbourList_info_for_min_hop(NeighbourList* list, const IDList* parents)
{
    uint16_t i;
    int mini = -1;
    uint16_t minhop = UINT16_MAX;

    //simdbg("stdout", "Finding neighbour info for closest hop...\n");

    for(i = 0; i<parents->count; i++)
    {
        NeighbourInfo* info = NeighbourList_get(list, parents->ids[i]);
        //simdbg("stdout", "Checking pparent %u.\n", parents->ids[i]);

        // If a node is a potential parent, we must have information on them.
        assert(info != NULL);

        //simdbg("stdout", "Retrieved id %u.\n", info->id);
        if(info->hop < minhop)
        {
            minhop = info->hop;
            mini = i;
        }
    }
    if(mini == -1)
    {
        //simdbg("stdout", "Failed to find neighbour info (parents size = %u)\n", parents->count);

        return NULL;
    }
    else
    {
        NeighbourInfo* mininfo = NeighbourList_get(list, parents->ids[mini]);

        simdbg("stdout", "Found min neighbour info: "); NeighbourInfo_print(mininfo); simdbg_clear("stdout", "\n");

        return mininfo;
    }
}

void NeighbourList_select(NeighbourList* list, const IDList* onehop, OnehopList* newList)
{
    int i;
    NeighbourList tempList = NeighbourList_new();
    for(i = 0; i< onehop->count; i++)
    {
        const NeighbourInfo* info = NeighbourList_get(list, onehop->ids[i]);
        if(info == NULL)
        {
            simdbgerror("stdout", "Attempted to include information for %u. But no information available.\n", onehop->ids[i]);
            continue;
        }
        NeighbourList_add_info(&tempList, info);
    }
    NeighbourList_to_OnehopList(&tempList, newList);
}

void NeighbourList_to_OnehopList(const NeighbourList* list, OnehopList *newList)
{
    if(list->count > MAX_ONEHOP)
    {
        simdbg("stdout", "NeighbourList too big to coerce to OnehopList. Truncating.\n");
    }
    newList->count = (list->count > MAX_ONEHOP) ? MAX_ONEHOP : list->count;
    memcpy(&(newList->info), &(list->info), MAX_ONEHOP * sizeof(NeighbourInfo));
}

void OnehopList_to_NeighbourList(const OnehopList* list, NeighbourList* newList)
{
    *newList = NeighbourList_new();
    newList->count = list->count;
    memcpy(&(newList->info), &(list->info), MAX_ONEHOP * sizeof(NeighbourInfo));
}

void NeighbourInfo_print(const NeighbourInfo* info)
{
    simdbg_clear("stdout", "(id=%u, slot=%u, hop=%u), ",
        info->id, info->slot, info->hop);
}

void OnehopList_print(const OnehopList* list)
{
    uint16_t i;
    simdbg_clear("stdout", "OnehopList size=%u [", list->count);
    for (i = 0; i < list->count; ++i)
    {
        NeighbourInfo_print(&list->info[i]);
    }
    simdbg_clear("stdout", "]");
}

void NeighbourList_print(const NeighbourList* list)
{
    uint16_t i;
    simdbg_clear("stdout", "NeighbourList size=%u [", list->count);
    for (i = 0; i < list->count; ++i)
    {
        NeighbourInfo_print(&list->info[i]);
    }
    simdbg_clear("stdout", "]");
}

OtherInfo OtherInfo_new(am_addr_t id)
{
    OtherInfo info;
    info.id = id;
    info.N = IDList_new();
    return info;
}

OtherList OtherList_new()
{
    OtherList list;
    list.count = 0;
    return list;
}

void OtherList_add(OtherList* list, OtherInfo info)
{
    uint16_t i;
    if(list->count >= MAX_TWOHOP) return;
    i = OtherList_indexOf(list, info.id);
    if(i == UINT16_MAX){
        i = list->count;
        list->count = list->count + 1;
    }
    list->info[i] = info;
}

uint16_t OtherList_indexOf(const OtherList* list, am_addr_t id)
{
    uint16_t i;
    for(i = 0; i < list->count; i++)
    {
        if(list->info[i].id == id) return i;
    }
    return UINT16_MAX;
}

OtherInfo* OtherList_get(OtherList* list, am_addr_t id)
{
    int i;
    for(i=0; i<list->count; i++)
    {
        if(list->info[i].id == id)
        {
            return &(list->info[i]);
        }
    }
    return NULL;
}
#endif /* UTILS_H */
