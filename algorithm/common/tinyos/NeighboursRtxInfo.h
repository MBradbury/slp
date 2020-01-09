#ifndef SLP_NEIGHBOURS_RTX_INFO_H
#define SLP_NEIGHBOURS_RTX_INFO_H

typedef struct 
{
	uint16_t rtx_success;
	uint16_t rtx_failure;

	uint16_t flags;

} NeighboursRtxInfo;

typedef enum
{
	NEIGHBOUR_INFO_PIN = (1 << 0)
} NeighboursRtxInfoFlags;

#endif // SLP_NEIGHBOURS_RTX_INFO_H
