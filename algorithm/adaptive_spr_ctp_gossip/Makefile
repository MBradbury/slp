COMPONENT = SourceBroadcasterAppC

CFLAGS += $(SLP_PARAMETER_CFLAGS)

CFLAGS += -I$(TOSDIR)/lib/net -I$(TOSDIR)/lib/net/ctp -I$(TOSDIR)/lib/net/drip -I$(TOSDIR)/lib/net/4bitle
CFLAGS += -I"../common/routing/gossip"

# Need to increase the size of the data to accommodate the beacon message
#CFLAGS += -DTOSH_DATA_LENGTH=44

include ../common/tinyos/makefile.common

#include $(TINYOS_ROOT_DIR)/Makefile.include
include $(MAKERULES)
