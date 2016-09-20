
#include "Common.h"

module SpanningTreeRoutingP
{
	provides interface RootControl;
}
implementation
{
	bool is_root = FALSE;

	command error_t RootControl.setRoot()
	{
		is_root = TRUE;
	}

    command error_t RootControl.unsetRoot()
    {
    	is_root = FALSE;
    }

    command bool RootControl.isRoot()
    {
    	return is_root;
    }
}
