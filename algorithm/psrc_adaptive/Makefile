COMPONENT = SourceBroadcasterAppC

CFLAGS += -Wnonnull -Wpointer-arith -Wshadow -Wformat -Werror=sign-compare

CFLAGS += $(SLP_PARAMETER_CFLAGS)

# Need to increase the size of the data to accommodate the normal message
CFLAGS += -DTOSH_DATA_LENGTH=32

CFLAGS += -I"../common"

#include $(TINYOS_ROOT_DIR)/Makefile.include
include $(MAKERULES)
