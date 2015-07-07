from __future__ import division

import collections

from simulator.Simulator import OutputCatcher

from data.restricted_eval import restricted_eval

# When an attacker receives any of these messages,
# do not check the seqno just move.
_messages_without_sequence_numbers = {'DummyNormal', 'Move', 'Beacon'}

# An attacker can detect these are not messages to follow,
# so the attacker will ignore these messages.
_messages_to_ignore = {'Beacon', 'Away', 'Move'}

class Attacker(object):
    def __init__(self):
        super(Attacker, self).__init__()
        self._sim = None
        self.position = None
        self._has_found_source = None
        self.moves = None

    def setup(self, sim, start_node_id):
        self._sim = sim

        out = OutputCatcher(self.process)
        out.register(self._sim, 'Attacker-RCV')
        self._sim.add_output_processor(out)

        self.position = None

        self._has_found_source = False

        # Create the moves variable and then make sure it
        # is set to 0 after the position has been set up.
        self.moves = 0
        self._move(start_node_id)
        self.moves = 0

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        raise NotImplementedError()

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        pass

    def process(self, line):
        # Don't want to move if the source has been found
        if self.found_source():
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = self._process_line(line)

        # We get called any time a message is received anywhere,
        # so first of all filter out messages being received by any node
        # other than the node the attacker is co-located with.

        # There are a number of message types an attacker will be able
        # to identify as protocol support messages. The attacker does not move
        # in response to these messages.

        if self.position == node_id and \
           msg_type not in _messages_to_ignore and \
           self.move_predicate(time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):

            self._move(prox_from_id)

            self.update_state(time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)
            
            self._draw(time, self.position)

    def found_source_slow(self):
        """Checks if the source has been found using the attacker's position."""
        # Well this is a horrible hack.
        # We cannot attach ourselves to the same output catcher more than
        # once, so we have to rely on metrics grabbing and updating
        # the information about which nodes are sources.
        return self.position in self._sim.metrics.source_ids

    def found_source(self):
        """Checks if the source has been found, using a cached variable."""
        return self._has_found_source

    def _move(self, node_id):
        """Moved the source to a new location."""
        self.position = node_id
        self._has_found_source = self.found_source_slow()

        self.moves += 1

    def _draw(self, time, node_id):
        """Updates the attacker position on the GUI if one is present."""
        if not self._sim.run_gui:
            return

        (x, y) = self._sim.node_location(node_id)

        shape_id = "attacker"

        color = '1,0,0'

        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)

        self._sim.scene.execute(time, 'delshape("{}")'.format(shape_id))
        self._sim.scene.execute(time, 'circle(%d,%d,5,ident="%s",%s)' % (x, y, shape_id, options))

    def _process_line(self, line):
        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = line.split(',')

        time = float(time) / self._sim.tossim.ticksPerSecond() # Get time to be in sec
        node_id = int(node_id)
        prox_from_id = int(prox_from_id)
        ult_from_id = int(ult_from_id)
        sequence_number = int(sequence_number)

        return (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)

    def __str__(self):
        return type(self).__name__ + "()"

class DeafAttacker(Attacker):
    """An attacker that does nothing when it receives a message"""
    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return False

class BasicReactiveAttacker(Attacker):
    """An attacker that reacts to every message that it should react to."""
    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return True

# Same as IgnorePastNLocationsReactiveAttacker(1)
class IgnorePreviousLocationReactiveAttacker(Attacker):
    def __init__(self):
        super(IgnorePreviousLocationReactiveAttacker, self).__init__()
        self._previous_location = None

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return self._previous_location != prox_from_id

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._previous_location = node_id

class IgnorePastNLocationsReactiveAttacker(Attacker):
    def __init__(self, memory_size):
        super(IgnorePastNLocationsReactiveAttacker, self).__init__()
        self._memory_size = memory_size
        self._previous_locations = collections.deque(maxlen=memory_size)

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return prox_from_id not in self._previous_locations

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._previous_locations.append(node_id)

    def __str__(self):
        return type(self).__name__ + "(memory_size={})".format(self._memory_size)

class TimeSensitiveReactiveAttacker(Attacker):
    def __init__(self, wait_time_secs):
        super(TimeSensitiveReactiveAttacker, self).__init__()
        self._previous_location = None
        self._last_moved_time = None
        self._wait_time_secs = wait_time_secs

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return self._last_moved_time is None or \
               abs(time - self._last_moved_time) >= self._wait_time_secs

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._previous_location = node_id
        self._last_moved_time = time

    def __str__(self):
        return type(self).__name__ + "(wait_time_secs={})".format(self._wait_time_secs)


# This attacker can determine the type of a message and its sequence number,
# but is unaware of the ultimate source of the message.
class SeqNoReactiveAttacker(Attacker):
    def __init__(self):
        super(SeqNoReactiveAttacker, self).__init__()
        self._sequence_numbers = {}

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (msg_type,)
        return msg_type in _messages_without_sequence_numbers or \
               seqno_key not in self._sequence_numbers or \
               self._sequence_numbers[seqno_key] < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (msg_type,)
        self._sequence_numbers[seqno_key] = sequence_number

# This attacker can determine the source node of certain messages
# that can be sent from multiple sources.
class SeqNosReactiveAttacker(Attacker):
    def __init__(self):
        super(SeqNosReactiveAttacker, self).__init__()
        self._sequence_numbers = {}

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        return msg_type in _messages_without_sequence_numbers or \
               seqno_key not in self._sequence_numbers or \
               self._sequence_numbers[seqno_key] < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number


def models():
    """A list of the the available attacker models."""
    return Attacker.__subclasses__()

def default():
    """Gets the the default attacker model"""
    return SeqNoReactiveAttacker()

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError("The source ({}) is not valid. (Did you forget the brackets after the name?)".format(source))

    if not isinstance(result, Attacker):
        raise RuntimeError("The source ({}) is not valid.".format(source))

    return result
