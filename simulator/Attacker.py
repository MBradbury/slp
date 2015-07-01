import collections

from simulator.Simulator import OutputCatcher

from data.restricted_eval import restricted_eval

# When an attacker receives any of these messages,
# do not check the seqno just move.
_messages_without_sequence_numbers = {'DummyNormal', 'Move', 'Beacon'}
_messages_to_ignore = {'Beacon'}

class Attacker(object):
    def __init__(self):
        self.sim = None
        self.position = None
        self.has_found_source = None
        self.moves = None

    def setup(self, sim, start_node_id):
        self.sim = sim

        out = OutputCatcher(self.process)
        out.register(self.sim, 'Attacker-RCV')
        self.sim.add_output_processor(out)

        self.position = None

        self.has_found_source = False

        # Create the moves variable and then make sure it
        # is set to 0 after the position has been set up.
        self.moves = 0
        self.move(start_node_id)
        self.moves = 0

    def process(self, line):
        raise NotImplementedError()

    def found_source_slow(self):
        """Checks if the source has been found using the attacker's position."""
        # Well this is a horrible hack.
        # We cannot attach ourselves to the same output catcher more than
        # once, so we have to rely on metrics grabbing and updating
        # the information about which nodes are sources.
        return self.position in self.sim.metrics.source_ids

    def found_source(self):
        """Checks if the source has been found, using a cached variable."""
        return self.has_found_source

    def move(self, node_id):
        """Moved the source to a new location."""
        self.position = node_id
        self.has_found_source = self.found_source_slow()

        self.moves += 1

    def draw(self, time, node_id):
        """Updates the attacker position on the GUI if one is present."""
        if not self.sim.run_gui:
            return

        (x, y) = self.sim.node_location(node_id)

        shape_id = "attacker"

        color = '1,0,0'

        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)

        self.sim.scene.execute(time, 'delshape("{}")'.format(shape_id))
        self.sim.scene.execute(time, 'circle(%d,%d,5,ident="%s",%s)' % (x, y, shape_id, options))

    def _process_line(self, line):
        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond() # Get time to be in sec
        node_id = int(node_id)
        prox_from_id = int(prox_from_id)
        ult_from_id = int(ult_from_id)
        sequence_number = int(sequence_number)

        return (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)

    def __str__(self):
        return type(self).__name__ + "()"

class DeafAttacker(Attacker):
    """An attacker that does nothing when it receives a message"""
    def process(self, line):
        pass

class BasicReactiveAttacker(Attacker):
    def process(self, line):
        # Don't want to move if the source has been found
        if self.found_source():
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = self._process_line(line)

        if self.position == node_id and msg_type not in _messages_to_ignore:

            self.move(prox_from_id)
            
            self.draw(time, self.position)

# Same as IgnorePastNLocationsReactiveAttacker(1)
class IgnorePreviousLocationReactiveAttacker(Attacker):
    def __init__(self):
        super(IgnorePreviousLocationReactiveAttacker, self).__init__()
        self.previous_location = None

    def process(self, line):
        # Don't want to move if the source has been found
        if self.found_source():
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = self._process_line(line)

        if self.position == node_id and \
            (msg_type in _messages_without_sequence_numbers or
            self.previous_location != prox_from_id) and \
            msg_type not in _messages_to_ignore:

            self.move(prox_from_id)

            self.draw(time, self.position)

    def move(self, node_id):
        self.previous_location = self.position
        super(IgnorePreviousLocationReactiveAttacker, self).move(node_id)

class IgnorePastNLocationsReactiveAttacker(Attacker):
    def __init__(self, memory_size):
        super(IgnorePastNLocationsReactiveAttacker, self).__init__()
        self.memory_size = memory_size
        self.previous_locations = collections.deque(maxlen=memory_size)

    def process(self, line):
        # Don't want to move if the source has been found
        if self.found_source():
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = self._process_line(line)

        if self.position == node_id and \
            (msg_type in _messages_without_sequence_numbers or
            prox_from_id not in self.previous_locations) and \
            msg_type not in _messages_to_ignore:

            self.move(prox_from_id)
            self.previous_locations.append(node_id)

            self.draw(time, self.position)

    def __str__(self):
        return type(self).__name__ + "(memory_size={})".format(self.memory_size)

class TimeSensitiveReactiveAttacker(Attacker):
    def __init__(self, wait_time_secs):
        super(TimeSensitiveReactiveAttacker, self).__init__()
        self.previous_location = None
        self.last_moved_time = None
        self.wait_time_secs = wait_time_secs

    def process(self, line):
        # Don't want to move if the source has been found
        if self.found_source():
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = self._process_line(line)

        if self.last_moved_time is not None and abs(time - self.last_moved_time) < self.wait_time_secs:
            return

        if self.position == node_id and \
            (msg_type in _messages_without_sequence_numbers or
            self.previous_location != prox_from_id) and \
            msg_type not in _messages_to_ignore:

            self.last_moved_time = time
            self.move(prox_from_id)

            self.draw(time, self.position)

    def move(self, node_id):
        self.previous_location = self.position
        super(TimeSensitiveReactiveAttacker, self).move(node_id)

    def __str__(self):
        return type(self).__name__ + "(wait_time_secs={})".format(self.wait_time_secs)


# This attacker can determine the type of a message and its sequence number,
# but is unaware of the ultimate source of the message.
class SeqNoReactiveAttacker(Attacker):
    def __init__(self):
        super(SeqNoReactiveAttacker, self).__init__()
        self.sequence_numbers = {}

    def process(self, line):
        # Don't want to move if the source has been found
        if self.found_source():
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = self._process_line(line)

        seqno_key = (msg_type,)

        if self.position == node_id and \
            (msg_type in _messages_without_sequence_numbers or
             seqno_key not in self.sequence_numbers or 
             self.sequence_numbers[seqno_key] < sequence_number) and \
            msg_type not in _messages_to_ignore:

            self.sequence_numbers[seqno_key] = sequence_number
            
            self.move(prox_from_id)

            self.draw(time, self.position)

# This attacker can determine the source node of certain messages
# that can be sent from multiple sources.
class SeqNosReactiveAttacker(Attacker):
    def __init__(self):
        super(SeqNosReactiveAttacker, self).__init__()
        self.sequence_numbers = {}

    def process(self, line):
        # Don't want to move if the source has been found
        if self.found_source():
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = self._process_line(line)

        seqno_key = (ult_from_id, msg_type)

        if self.position == node_id and \
            (msg_type in _messages_without_sequence_numbers or
             seqno_key not in self.sequence_numbers or 
             self.sequence_numbers[seqno_key] < sequence_number) and \
            msg_type not in _messages_to_ignore:

            self.sequence_numbers[seqno_key] = sequence_number
            
            self.move(prox_from_id)

            self.draw(time, self.position)

def models():
    """A list of the the available attacker models."""
    return [cls for cls in Attacker.__subclasses__()]

def default():
    """Gets the the default attacker model"""
    return SeqNoReactiveAttacker()

def eval_input(source):
    result = restricted_eval(source, models())

    if not isinstance(result, Attacker):
        raise RuntimeError("The source ({}) is not valid.".format(source))

    return result
