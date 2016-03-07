COMPONENT = SourceBroadcasterAppC

# See http://www.ti.com/lit/ds/symlink/cc2420.pdf
# Section 28
#CFLAGS += -DCC2420_DEF_RFPOWER=31
#CFLAGS += -DCC2420X_DEF_RFPOWER=1

CFLAGS += $(SLP_PARAMETER_CFLAGS)

# Need to increase data to accomodate WaveMessage 48
CFLAGS += -DTOSH_DATA_LENGTH=964

CFLAGS += -I"../common"

include ../common/makefile.common

#include $(TINYOS_ROOT_DIR)/Makefile.include
include $(MAKERULES)
