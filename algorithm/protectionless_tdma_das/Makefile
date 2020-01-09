COMPONENT = SourceBroadcasterAppC

# See http://www.ti.com/lit/ds/symlink/cc2420.pdf
# Section 28
#CFLAGS += -DCC2420_DEF_RFPOWER=31
#CFLAGS += -DCC2420X_DEF_RFPOWER=1

CFLAGS += $(SLP_PARAMETER_CFLAGS)

CFLAGS += -DTOSH_DATA_LENGTH=61

PFLAGS += -I$(TOSDIR)/lib/ftsp
CFLAGS += -DTIMESYNC_ENTRY_VALID_LIMIT=4 -DTIMESYNC_ENTRY_SEND_LIMIT=1

include ../common/tinyos/makefile.common

#include $(TINYOS_ROOT_DIR)/Makefile.include
include $(MAKERULES)
