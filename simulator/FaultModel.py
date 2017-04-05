from __future__ import division, print_function

from data.restricted_eval import restricted_eval

class FaultModel(object):
    def __init__(self):
        self.sim = None

    def setup(self, sim):
        self.sim = sim

    def __str__(self):
        return type(self).__name__ + "()"

class ReliableFaultModel(FaultModel):
    """The default fault mobility model, nothing bad happens."""
    def __init__(self):
        super(ReliableFaultModel, self).__init__()

class NodeCrashFaultModel(FaultModel):
    """This model will crash the specified node at the specified time."""
    def __init__(self, node_id, crash_time):
        super(NodeCrashFaultModel, self).__init__()

        # The node to crash, this may be a string representing a landmark node
        self.node_id = node_id

        # The node to crash converted to a topology node id
        self.topo_converted_node_id = None

        # The time at which to crash the node
        self.crash_time = crash_time

    def setup(self, sim):
        super(NodeCrashFaultModel, self).setup(sim)

        # convert the provided node id to a topology node id.
        # For example the node_id might be 'sink_id', this will convert it
        # to the correct id.
        self.topo_converted_node_id = sim.configuration.get_node_id(self.node_id)

        # Add an event to be called
        self.sim.register_event_callback(self._crash_event, self.crash_time)

    def _crash_event(self, current_time):
        node = self.sim.node_from_topology_nid(self.topo_converted_node_id)

        # Turn off the mote to simulate a crash
        node.tossim_node.turnOff()

        #print("M-FM:{},{},{}".format(self.topo_converted_node_id, node.nid, current_time))

    def __str__(self):
        return type(self).__name__ + "(node_id={!r}, crash_time={})".format(self.node_id, self.crash_time)

def models():
    """A list of the available models."""
    return FaultModel.__subclasses__() # pylint: disable=no-member

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError("The fault model ({}) is not valid. (Did you forget the brackets after the name?)".format(source))

    if not isinstance(result, FaultModel):
        raise RuntimeError("The fault model ({}) is not valid.".format(source))

    return result
