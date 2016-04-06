from __future__ import division

import collections

import numpy as np

from simulator.Simulation import OutputCatcher

from data.restricted_eval import restricted_eval

# When an attacker receives any of these messages,
# do not check the seqno just move.
_messages_without_sequence_numbers = {'DummyNormal', 'Move', 'Beacon', 'CTPBeacon'}

# An attacker can detect these are not messages to follow,
# so the attacker will ignore these messages.
_messages_to_ignore = {'Beacon', 'Away', 'Move', 'Choose', 'Dissem', 'CTPBeacon'}

class Attacker(object):
    def __init__(self):
        self._sim = None
        self.position = None
        self._has_found_source = None
        self.moves = None
        self.ident = None

        # Metric initialisation from here onwards
        self.steps_towards = {}
        self.steps_away = {}

        self.min_source_distance = {}

    def setup(self, sim, start_node_id, ident):
        self._sim = sim
        self.ident = ident

        out = OutputCatcher(self.process)
        out.register(self._sim, 'Attacker-RCV')
        self._sim.add_output_processor(out)

        self.position = start_node_id
        self._has_found_source = self.found_source_slow()
        self.moves = 0

        self.steps_towards = {source: 0 for source in self._source_ids()}
        self.steps_away = {source: 0 for source in self._source_ids()}

        self.min_source_distance = {source: self._sim.node_distance(start_node_id, source) for source in self._source_ids()}

        self.setup_event_callbacks()

    def _source_ids(self):
        return self._sim.metrics.source_ids

    def setup_event_callbacks(self):
        pass

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        raise NotImplementedError()

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        pass

    def process(self, line):
        # Don't want to move if the source has been found
        if self._has_found_source:
            return

        (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = line.split(',')

        node_id = int(node_id)

        # Doesn't want to process this message if we are not on the correct node,
        # or if this is a message the attacker knows to ignore
        if self.position != node_id or msg_type in _messages_to_ignore:
            return

        time = self._sim.ticks_to_seconds(float(time))
        prox_from_id = int(prox_from_id)
        ult_from_id = int(ult_from_id)
        sequence_number = int(sequence_number)

        # We get called any time a message is received anywhere,
        # so first of all filter out messages being received by any node
        # other than the node the attacker is co-located with.

        # There are a number of message types an attacker will be able
        # to identify as protocol support messages. The attacker does not move
        # in response to these messages.

        if self.move_predicate(time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):

            self._move(time, prox_from_id)

            self.update_state(time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)

    def found_source_slow(self):
        """Checks if the source has been found using the attacker's position."""
        # Well this is a horrible hack.
        # We cannot attach ourselves to the same output catcher more than
        # once, so we have to rely on metrics grabbing and updating
        # the information about which nodes are sources.
        return self.position in self._source_ids()

    def found_source(self):
        """Checks if the source has been found, using a cached variable."""
        return self._has_found_source

    def _move(self, time, node_id):
        """Moved the source to a new location."""

        self.moves += 1

        for source in self._source_ids():
            new_distance = self._sim.node_distance(source, node_id)
            old_distance = self._sim.node_distance(source, self.position)

            if new_distance > old_distance:
                self.steps_away[source] += 1
            elif new_distance < old_distance:
                self.steps_towards[source] += 1

            self.min_source_distance[source] = min(self.min_source_distance[source], new_distance)

        self.position = node_id
        self._has_found_source = self.found_source_slow()

        # Update the simulator, informing them that an attacker has found the source
        self._sim.attacker_found_source |= self._has_found_source

        self._draw(time, self.position)

    def _draw(self, time, node_id):
        """Updates the attacker position on the GUI if one is present."""
        if not hasattr(self._sim, "scene"):
            return

        (x, y) = self._sim.node_location(node_id)

        shape_id = "attacker{}".format(self.ident)

        color = '1,0,0'

        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)

        self._sim.scene.execute(time, 'delshape("{}")'.format(shape_id))
        self._sim.scene.execute(time, 'circle(%d,%d,5,ident="%s",%s)' % (x, y, shape_id, options))

    def __str__(self):
        return type(self).__name__ + "()"

class DeafAttacker(Attacker):
    """An attacker that does nothing when it receives a message"""
    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return False

class DeafAttackerWithEvent(Attacker):
    """An attacker that does nothing when it receives a message.
    This attacker also inserts a callback every period seconds."""
    def __init__(self, period):
        super(DeafAttackerWithEvent, self).__init__()
        self._period = period

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return False

    def setup_event_callbacks(self):
        self._sim.tossim.register_event_callback(self._callback, self._period)

    def _callback(self, current_time):
        self._sim.tossim.register_event_callback(self._callback, current_time + self._period)

    def __str__(self):
        return type(self).__name__ + "(period={})".format(self._period)

class BasicReactiveAttacker(Attacker):
    """An attacker that reacts to every message that it should react to."""
    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return True

class IgnorePreviousLocationReactiveAttacker(Attacker):
    """
    Same as IgnorePastNLocationsReactiveAttacker(1)
    """

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



class SeqNoReactiveAttacker(Attacker):
    """
    This attacker can determine the type of a message and its sequence number,
    but is unaware of the ultimate source of the message.
    """

    def __init__(self):
        super(SeqNoReactiveAttacker, self).__init__()
        self._sequence_numbers = {}

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = msg_type
        return msg_type in _messages_without_sequence_numbers or \
               self._sequence_numbers.get(seqno_key, -1) < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = msg_type
        self._sequence_numbers[seqno_key] = sequence_number

class SeqNosReactiveAttacker(Attacker):
    """
    This attacker can determine the source node of certain messages
    that can be sent from multiple sources.
    """
    def __init__(self):
        super(SeqNosReactiveAttacker, self).__init__()
        self._sequence_numbers = {}

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        return msg_type in _messages_without_sequence_numbers or \
               self._sequence_numbers.get(seqno_key, -1) < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number


class SingleTypeReactiveAttacker(Attacker):
    """
    This attacker is only reacts to receiving specific messages.
    It also has access to the ultimate sender and sequence number header fields.
    """
    def __init__(self, msg_type):
        super(SingleTypeReactiveAttacker, self).__init__()
        self._sequence_numbers = {}
        self._msg_type = msg_type

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        return msg_type == self._msg_type and \
               self._sequence_numbers.get(seqno_key, -1) < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number

class CollaborativeSeqNosReactiveAttacker(Attacker):
    def __init__(self):
        super(CollaborativeSeqNosReactiveAttacker, self).__init__()
        self._sequence_numbers = {}

    def _other_attackers_responded(self, seqno_key, sequence_number):
        others = [attacker for attacker in self._sim.attackers if attacker is not self]

        for attacker in others:
            if attacker._sequence_numbers.get(seqno_key, -1) >= sequence_number:
                return True

        return False

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        return msg_type in _messages_without_sequence_numbers or \
               (not self._other_attackers_responded(seqno_key, sequence_number) and
                self._sequence_numbers.get(seqno_key, -1) < sequence_number)

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number

class TimedBacktrackingAttacker(Attacker):
    """An attacker that backtracks to the previous node after a certain amount of time where no messages are received."""
    def __init__(self, wait_time_secs):
        super(TimedBacktrackingAttacker, self).__init__()
        self._wait_time_secs = wait_time_secs

        self._sequence_numbers = {}
        self._last_move_time = None
        self._previous_location = None

    def _move_to_previous_location_on_timeout(self, time):
        if self._last_move_time is not None and self._previous_location is not None and np.isclose(time, self._last_move_time + self._wait_time_secs):
            self._move(time, self._previous_location)

            self._last_move_time = time
            self._previous_location = None

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        return msg_type in _messages_without_sequence_numbers or \
               self._sequence_numbers.get(seqno_key, -1) < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number

        self._last_move_time = time
        self._previous_location = node_id

        self._sim.tossim.register_event_callback(self._move_to_previous_location_on_timeout, time + self._wait_time_secs)

    def __str__(self):
        return type(self).__name__ + "(wait_time_secs={})".format(self._wait_time_secs)

class ABDAttacker(Attacker):
    def __init__(self, period, messages_per_period, history_window):
        super(ABDAttacker, self).__init__()

        self._period = period
        self._messages_per_period = messages_per_period
        self._history_window = history_window

        self._previous_location = None
        self._messages = []

    def setup_event_callbacks(self):
        self._sim.tossim.register_event_callback(self._clear_messages, self._period)

    def _clear_messages(self, current_time):
        self._messages = []

        print("Cleared messages at {}".format(current_time))

        self._sim.tossim.register_event_callback(self._clear_messages, current_time + self._period)

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return True

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        pass

    def __str__(self):
        return type(self).__name__ + "(period={},messages_per_period={},history_window={})".format(
            self._period, self._messages_per_period, self._history_window)

def models():
    """A list of the the available attacker models."""
    return Attacker.__subclasses__()

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError("The source ({}) is not valid. (Did you forget the brackets after the name?)".format(source))

    if not isinstance(result, Attacker):
        raise RuntimeError("The source ({}) is not a valid instance of an Attacker.".format(source))

    return result
