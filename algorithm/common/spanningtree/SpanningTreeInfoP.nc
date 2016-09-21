
module SpanningTreeInfoP
{
	provides interface SpanningTreeInfo;

	provides interface RootControl;
}

implementation
{
	am_addr_t parent = AM_BROADCAST_ADDR;

	command am_addr_t SpanningTreeInfo.get_parent()
	{
		return parent;
	}

	command void SpanningTreeInfo.set_parent(am_addr_t new_parent)
	{
		parent = new_parent;
	}



	bool is_root = FALSE;

	command error_t RootControl.setRoot()
	{
		is_root = TRUE;
		return SUCCESS;
	}

    command error_t RootControl.unsetRoot()
    {
    	is_root = FALSE;
    	return SUCCESS;
    }

    command bool RootControl.isRoot()
    {
    	return is_root;
    }
}
