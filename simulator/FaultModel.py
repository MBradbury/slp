from __future__ import division, print_function

import sys

from data.restricted_eval import restricted_eval

class FaultModel(object):
    def __init__(self, requires_nesc_variables=False):
        self.sim = None
        self._has_gui = False
        self.requires_nesc_variables = requires_nesc_variables

        # Record how many faults have occurred
        self.faults_occurred = 0

    def setup(self, sim):
        self.sim = sim
        self._has_gui = hasattr(sim, "gui")

    def build_arguments(self):
        return {
            "SLP_NO_FAULT_MODEL": 1
        }

    def _draw(self):
        return

    def __str__(self):
        return type(self).__name__ + "()"

    def short_name(self):
        return str(self)

class FaultPointModel(FaultModel):
    def __init__(self, fault_point_probs, base_probability=0.0, requires_nesc_variables=False):
        super(FaultPointModel, self).__init__(requires_nesc_variables=requires_nesc_variables)
        self.fault_points = {}
        self.fault_point_probs = fault_point_probs if fault_point_probs is not None else {}
        self.base_probability = base_probability

    def setup(self, sim):
        super(FaultPointModel, self).setup(sim)
        sim.register_output_handler("M-FPA", self._fault_point_add)
        sim.register_output_handler("M-FP", self._fault_point_occurred)

    def build_arguments(self):
        return {
            "SLP_TOSSIM_FAULT_MODEL": 1
        }

    def _fault_point_add(self, log_type, node_id, current_time, detail):
        fault_point_id, fault_point_name = detail.split(",")
        fault_point_id = int(fault_point_id)

        self.fault_points[fault_point_id] = fault_point_name

    def _fault_point_occurred(self, log_type, node_id, current_time, detail):
        fault_point_id = int(detail)
        try:
            fault_point_name = self.fault_points[fault_point_id]
        except KeyError:
            print("A fault point (with id {}) occurred that was not previously added.".format(fault_point_id), file=sys.stderr)
            return

        probability = self.fault_point_probs.get(fault_point_name, self.base_probability)

        if self.sim.rng.random() < probability:
            node_id = int(node_id)
            node = self.sim.node_from_ordered_nid(node_id)
            self.fault_occurred(fault_point_name, node)

            self.faults_occurred += 1

            if self._has_gui:
                self._draw(node_id)

    def fault_occurred(self, fault_point_name, node):
        raise NotImplementedError("FaultPointModel subclass must implement fault_occurred function")

    def _draw(self, node_id):
        """Marks all nodes that have faulted in the GUI."""
        (x, y) = self.sim.gui.node_location(node_id)
        shape_id = "faultednode{}".format(node_id)
        color = "0,0,0"
        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)
        time = self.sim.sim_time()

        self.sim.gui.scene.execute(time, 'delshape({!r})'.format(shape_id))
        self.sim.gui.scene.execute(time, 'circle({},{},5,ident={!r},{})'.format(x, y, shape_id, options))

    def __str__(self):
        return "{}(fault_point_probs={},base_probability={})".format(
            type(self).__name__, self.fault_point_probs, self.base_probability)

    def short_name(self):
        return "{}({},{})".format(
            type(self).__name__.replace("FaultPointModel", "FPM"), self.fault_point_probs, self.base_probability)

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

        self.faults_occurred += 1

    def __str__(self):
        return "{}(node_id={!r}, crash_time={})".format(type(self).__name__, self.node_id, self.crash_time)

class NodeCrashVariableFaultModel(FaultModel):
    """This model will crash any node with a specified variable set to the given value."""
    def __init__(self, variable_name, variable_value, check_interval=1):
        super(NodeCrashVariableFaultModel, self).__init__(requires_nesc_variables=True)

        # The name of the variable to watch
        self.variable_name = variable_name

        # Set the value the variable must be for the node to crash
        self.variable_value = variable_value

        # The interval between checking each node's specified variable
        self.check_interval = check_interval

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

                self.faults_occurred += 1

        # Add next event
        self.sim.register_event_callback(self._check_variables, current_time + self.check_interval)

    def __str__(self):
        return "{}(variable_name={}, variable_value={}, check_interval={})".format(
            type(self).__name__, self.variable_name, self.variable_value, self.check_interval)

class NodeCrashTypeFaultModel(FaultModel):
    """This model will listen for a node change event changing to 'CrashNode' in order to crash that node."""

    def __init__(self):
        super(NodeCrashTypeFaultModel, self).__init__()

    def setup(self, sim):
        super(NodeCrashTypeFaultModel, self).setup(sim)

        # Register a listener for node change events
        sim.register_output_handler("M-NC", self._crash_node_listener)

    def _crash_node_listener(self, log_type, node_id, current_time, detail):
        (from_node_type, to_node_type) = detail.split(",")

        if to_node_type == "CrashNode":
            node = self.sim.node_from_ordered_nid(int(node_id))
            #print("Turning off node {} to simulate crash because node_type=CrashNode".format(int(node_id)), file=sys.stderr)
            node.tossim_node.turnOff()

            self.faults_occurred += 1

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

        self.faults_occurred += 1

    def __str__(self):
        return "{}(node_id={!r}, variable_name={!r}, flip_time={})".format(
            type(self).__name__, self.node_id, self.variable_name, self.flip_time)

class NodeCrashFaultPointModel(FaultPointModel):
    """This model will crash a node at the fault point."""
    def __init__(self, fault_point_probs, base_probability=0.0):
        super(NodeCrashFaultPointModel, self).__init__(fault_point_probs, base_probability=base_probability)

    def fault_occurred(self, fault_point_name, node):
        # On fault, turn node off to simulate crash
        node.tossim_node.turnOff()

class BitFlipFaultPointModel(FaultPointModel):
    """This model will flip a bit in a specified variable at the fault point."""
    def __init__(self, fault_point_probs, variable, base_probability=0.0):
        super(BitFlipFaultPointModel, self).__init__(fault_point_probs, base_probability=base_probability, requires_nesc_variables=True)
        self.variable = variable

    def setup(self, sim):
        super(BitFlipFaultModel, self).setup(sim)

        # Check variable actually exists before starting
        sim.node_from_ordered_nid(0).tossim_node.getVariable(self.variable)

    def fault_occurred(self, fault_point_name, node):
        # Get the node's variable
        variable = node.tossim_node.getVariable(self.variable)

        # Get the data
        data = variable.getData()

        # Flip a bit in the data
        new_data = data ^ 1

        # Reassign the data
        variable.setData(new_data)

    def __str__(self):
        return "{}(fault_point_probs={},variable={},base_probability={})".format(type(self).__name__,
                self.fault_point_probs, self.variable, self.base_probability)

class NescFaultModel(FaultModel):
    """Wires up a NesC Fault Model."""
    def __init__(self, fault_model_name):
        super(NescFaultModel, self).__init__()

        self.fault_model_name = fault_model_name

    def build_arguments(self):
        return {
            "SLP_NESC_FAULT_MODEL": self.fault_model_name
        }

    def __str__(self):
        return "{}(fault_model_name={!r})".format(
            type(self).__name__, self.fault_model_name)


def models():
    """A list of the available models."""
    return [
        f
        for f
        in FaultModel.__subclasses__() + FaultPointModel.__subclasses__() # pylint: disable=no-member
        if f is not FaultPointModel
    ]

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError("The fault model ({}) is not valid. (Did you forget the brackets after the name?)".format(source))

    if not isinstance(result, FaultModel):
        raise RuntimeError("The fault model ({}) is not valid.".format(source))

    return result

def available_models():
    class WildcardModelChoice(object):
        """A special available model that checks if the string provided
        matches the name of the class."""
        def __init__(self, cls):
            self.cls = cls

        def __eq__(self, value):
            return isinstance(value, self.cls)

        def __repr__(self):
            return self.cls.__name__ + "(...)"

    return [WildcardModelChoice(x) for x in models()]
