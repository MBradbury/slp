COMPONENT = SourceBroadcasterAppC

CFLAGS += -DPACKET_LINK=1

CFLAGS += -Wnonnull -Wpointer-arith -Wshadow -Wformat -Werror=sign-compare

CFLAGS += $(SLP_PARAMETER_CFLAGS)

# Need to increase the size of the data to accommodate the normal message
CFLAGS += -DTOSH_DATA_LENGTH=48

CFLAGS += -I"../common"

#include $(TINYOS_ROOT_DIR)/Makefile.include
include $(MAKERULES)
