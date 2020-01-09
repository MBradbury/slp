COMPONENT = SourceBroadcasterAppC

# See http://www.ti.com/lit/ds/symlink/cc2420.pdf
# Section 28
#CFLAGS += -DCC2420_DEF_RFPOWER=31
#CFLAGS += -DCC2420X_DEF_RFPOWER=1

CFLAGS += $(SLP_PARAMETER_CFLAGS)

CFLAGS += -I"../common" -I"../common/spanningtree" -I$(TOSDIR)/lib/net -I$(TOSDIR)/lib/net/le

include ../common/tinyos/makefile.common

#include $(TINYOS_ROOT_DIR)/Makefile.include
include $(MAKERULES)
