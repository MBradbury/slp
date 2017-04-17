from __future__ import division, print_function

#import sys

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

        #print("Turning off node (topo: {}, ord: {}) to simulate a crash".format(self.node_id, node.nid), file=sys.stderr)

        # Turn off the mote to simulate a crash
        node.tossim_node.turnOff()

    def __str__(self):
        return "{}(node_id={!r}, crash_time={})".format(type(self).__name__, self.node_id, self.crash_time)

class NodeCrashVariableFaultModel(FaultModel):
    """This model will crash any node with a specified variable set to the given value."""
    def __init__(self, variable_name, variable_value):
        super(NodeCrashVariableFaultModel, self).__init__()

        # The name of the variable to watch
        self.variable_name = variable_name

        # Set the value the variable must be for the node to crash
        self.variable_value = variable_value

        # The interval between checking each node's specified variable
        self.check_interval = 1

        # Dict of (Variable object, node id) for all nodes
        self.variables = None

    def setup(self, sim):
        super(NodeCrashVariableFaultModel, self).setup(sim)

        # Create the dict of variables and node ids
        self.variables = {}
        for node in self.sim.nodes:
            # self.variables[node.tossim_node.getVariable(self.variable_name)] = sim.configuration.get_node_id(node.nid)
            self.variables[node.tossim_node.getVariable(self.variable_name)] = node.nid

        # Add first event
        self.sim.register_event_callback(self._check_variables, self.check_interval)

    def _check_variables(self, current_time):
        # Check each variable to see if it is equal to the failure value
        for v in self.variables.keys():
            if v.getData() == self.variable_value:
                # node = self.sim.node_from_topology_nid(self.variables[v])
                node = self.sim.node_from_ordered_nid(self.variables[v])
                #print("Turning off node {} to simulate a crash because variable {}={}".format(node.nid, self.variable_name, self.variable_value), file=sys.stderr)
                node.tossim_node.turnOff()
                del self.variables[v]

        # Add next event
        self.sim.register_event_callback(self._check_variables, current_time + self.check_interval)

    def __str__(self):
        return "{}(variable_name={},variable_value={})".format(type(self).__name__, self.variable_name, self.variable_value)

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

        # Add an event to be called
        self.sim.register_event_callback(self._flip_event, self.flip_time)

    def _flip_event(self, current_time):
        # Get the data
        data = self.variable.getData()

        # Flip a bit in the data
        new_data = data ^ 1

        # Reassign the data
        self.variable.setData(new_data)

        #print("Setting variable {} on {} to {} from {} simulate a bit flip".format(
        #    self.variable_name, self.node_id, new_data, data), file=sys.stderr)

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
