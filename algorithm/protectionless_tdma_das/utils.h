#ifndef UTILS_H
#define UTILS_H

#include "Constants.h"

#include <string.h>

#define MAX_ONEHOP SLP_MAX_1_HOP_NEIGHBOURHOOD
#define MAX_TWOHOP SLP_MAX_2_HOP_NEIGHBOURHOOD

typedef nx_struct IDList {
    nx_uint16_t count;
    nx_uint16_t ids[MAX_TWOHOP];
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
void IDList_add(IDList* list, uint16_t id);
void IDList_sort(IDList* list);
uint16_t IDList_indexOf(IDList* list, uint16_t el);
IDList IDList_minus_parent(IDList* list, uint16_t parent);
void IDList_clear(IDList* list);

uint16_t rank(IDList* list, uint16_t id);

NeighbourInfo NeighbourInfo_new(uint16_t id, int hop, int slot);
NeighbourList NeighbourList_new();
void NeighbourList_add(NeighbourList* list, uint16_t id, int hop, int slot);
void NeighbourList_add_info(NeighbourList* list, NeighbourInfo info);
uint16_t NeighbourList_indexOf(const NeighbourList* list, uint16_t id);
NeighbourInfo* NeighbourList_get(NeighbourList* list, uint16_t id);
NeighbourInfo* NeighbourList_min_h(NeighbourList* list, IDList* parents);
void NeighbourList_select(NeighbourList* list, IDList* onehop, OnehopList* newList);
void NeighbourList_to_OnehopList(NeighbourList* list, OnehopList *newList);
void OnehopList_to_NeighbourList(OnehopList* list, NeighbourList* newList);

OtherInfo OtherInfo_new(uint16_t id);
OtherList OtherList_new();
void OtherList_add(OtherList* list, OtherInfo info);
uint16_t OtherList_indexOf(const OtherList* list, uint16_t id);
OtherInfo* OtherList_get(OtherList* list, uint16_t id);


IDList IDList_new()
{
    IDList list;
    list.count = 0;
    return list;
}

void IDList_add(IDList* list, uint16_t id)
{
    if(list->count >= MAX_TWOHOP)
    {
        simdbg("stdout", "IDList is full\n");
        return;
    }
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

uint16_t rank(IDList* list, uint16_t id)
{
    uint16_t i;
    IDList_sort(list);
    i = IDList_indexOf(list, id);
    if(i == UINT16_MAX) return UINT16_MAX;
    else return i+1;
}




NeighbourInfo NeighbourInfo_new(uint16_t id, int hop, int slot)
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

void NeighbourList_add(NeighbourList* list, uint16_t id, int hop, int slot)
{
    uint16_t i;
    i = NeighbourList_indexOf(list, id);
    if(i == UINT16_MAX){
        if(list->count >= MAX_TWOHOP)
        {
            simdbg("stdout", "NeighbourList is full.\n");
            return;
        }
        i = list->count;
        list->count = list->count + 1;
    }
    list->info[i] = NeighbourInfo_new(id, hop, slot);
}

void NeighbourList_add_info(NeighbourList* list, NeighbourInfo info)
{
    uint16_t i;
    i = NeighbourList_indexOf(list, info.id);
    if(i == UINT16_MAX){
        if(list->count >= MAX_TWOHOP)
        {
            simdbg("stdout", "NeighbourList is full.\n");
            return;
        }
        i = list->count;
        list->count = list->count + 1;
    }
    list->info[i] = info;
}

uint16_t NeighbourList_indexOf(const NeighbourList* list, uint16_t id)
{
    uint16_t i;
    for(i = 0; i < list->count; i++)
    {
        if(list->info[i].id == id) return i;
    }
    return UINT16_MAX;
}

NeighbourInfo* NeighbourList_get(NeighbourList* list, uint16_t id)
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

NeighbourInfo* NeighbourList_min_h(NeighbourList* list, IDList* parents)
{
    uint16_t i;
    int mini = -1;
    uint16_t minhop = UINT16_MAX;
    for(i = 0; i<parents->count; i++)
    {
        NeighbourInfo* info = NeighbourList_get(list, parents->ids[i]);
        //simdbg("stdout", "Checking pparent %u.\n", parents->ids[i]);
        if(info == NULL) continue;
        //simdbg("stdout", "Retrieved id %u.\n", info->id);
        if(info->hop < minhop)
        {
            minhop = info->hop;
            mini = i;
        }
    }
    if(mini == -1)
    {
        return NULL;
    }
    else
    {
        return NeighbourList_get(list, parents->ids[mini]);
    }
}

void NeighbourList_select(NeighbourList* list, IDList* onehop, OnehopList* newList)
{
    int i;
    NeighbourList tempList = NeighbourList_new();
    for(i = 0; i< onehop->count; i++)
    {
        NeighbourInfo* info = NeighbourList_get(list, onehop->ids[i]);
        if(info == NULL) continue;
        NeighbourList_add_info(&tempList, *info);
    }
    NeighbourList_to_OnehopList(&tempList, newList);
}

void NeighbourList_to_OnehopList(NeighbourList* list, OnehopList *newList)
{
    if(list->count > MAX_ONEHOP)
    {
        simdbg("stdout", "NeighbourList too big to coerce to OnehopList. Truncating.\n");
    }
    newList->count = (list->count > MAX_ONEHOP) ? MAX_ONEHOP : list->count;
    memcpy(&(newList->info), &(list->info), MAX_ONEHOP * sizeof(NeighbourInfo));
}

void OnehopList_to_NeighbourList(OnehopList* list, NeighbourList* newList)
{
    *newList = NeighbourList_new();
    newList->count = list->count;
    memcpy(&(newList->info), &(list->info), MAX_ONEHOP * sizeof(NeighbourInfo));
}

OtherInfo OtherInfo_new(uint16_t id)
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

uint16_t OtherList_indexOf(const OtherList* list, uint16_t id)
{
    uint16_t i;
    for(i = 0; i < list->count; i++)
    {
        if(list->info[i].id == id) return i;
    }
    return UINT16_MAX;
}

OtherInfo* OtherList_get(OtherList* list, uint16_t id)
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
