from __future__ import division, print_function

from data.restricted_eval import restricted_eval

class FaultModel(object):
    def __init__(self, requires_nesc_variables=False):
        self.sim = None
        self.requires_nesc_variables = requires_nesc_variables

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

    def __str__(self):
        return "{}(node_id={!r}, crash_time={})".format(type(self).__name__, self.node_id, self.crash_time)

class BitFlipFaultModel(FaultModel):
    """This model will flip a bit in the specified variable on the specified node at the specified time."""
    def __init__(self, node_id, variable_name, flip_time):
        super(BitFlipFaultModel, self).__init__(requires_nesc_variables=True)

        # The node on which to flip a bit, this may be a string representing a landmark node
        self.node_id = node_id

        self.variable_name = variable_name

        # The node converted to a topology node id
        self.topo_converted_node_id = None

        self.variable = None

        # The time at which to flip the bit
        self.flip_time = flip_time

    def setup(self, sim):
        super(BitFlipFaultModel, self).setup(sim)

        # convert the provided node id to a topology node id.
        # For example the node_id might be 'sink_id', this will convert it
        # to the correct id.
        self.topo_converted_node_id = sim.configuration.get_node_id(self.node_id)

        # Check the variable name is correct
        node = self.sim.node_from_topology_nid(self.topo_converted_node_id)
        self.variable = node.tossim_node.getVariable(self.variable_name)

        if self.variable.getData() == "<no such variable>":
            raise RuntimeError("Tossim was unable to find the variable '{}'.".format(self.variable_name))

        # Add an event to be called
        self.sim.register_event_callback(self._flip_event, self.flip_time)

    def _flip_event(self, current_time):
        # Get the data
        data = self.variable.getData()

        # Flip a bit in the data
        data ^= 1

        # Reassign the data
        self.variable.setData(data)

    def __str__(self):
        return "{}(node_id={!r}, variable_name={!r}, flip_time={})".format(
            type(self).__name__, self.node_id, self.variable_name, self.flip_time)

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
