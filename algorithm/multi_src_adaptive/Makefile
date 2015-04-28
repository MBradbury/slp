COMPONENT = SourceBroadcasterAppC

CFLAGS += -Wnonnull -Wpointer-arith -Wshadow -Wformat

CFLAGS += $(SLP_PARAMETER_CFLAGS)

CFLAGS += -I"../common"

# Need to increase the size of the data to accommodate the normal message
CFLAGS += -DTOSH_DATA_LENGTH=48

#include $(TINYOS_ROOT_DIR)/Makefile.include
include $(MAKERULES)
