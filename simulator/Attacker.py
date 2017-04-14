from __future__ import print_function, division

from collections import Counter, deque

import numpy as np

from data.restricted_eval import restricted_eval

# When an attacker receives any of these messages,
# do not check the seqno just move.
MESSAGES_WITHOUT_SEQUENCE_NUMBERS = {
    'DummyNormal', 'Move', 'Beacon', 'CTPBeacon',
    'Inform', 'Search', 'Change', 'EmptyNormal', 'Poll',
}

# An attacker can detect these are not messages to follow,
# so the attacker will ignore these messages.
MESSAGES_TO_IGNORE = {
    'Beacon', 'Away', 'Move', 'Choose', 'Dissem',
    'CTPBeacon', 'Inform', 'Search', 'Change',
    'Poll', 'Notify',
}

class Attacker(object):
    def __init__(self):
        self._sim = None
        self.position = None
        self._has_found_source = None
        self.moves = None
        self.ident = None
        self._has_gui = False

        # Metric initialisation from here onwards
        self.steps_towards = Counter()
        self.steps_away = Counter()

        self.normal_receive_time = {}

        self.moves_in_response_to = Counter()

        self.min_source_distance = {}

    def setup(self, sim, start_node_id, ident):
        self._sim = sim
        self.ident = ident

        self._sim.register_output_handler('A-R', self.process_attacker_rcv_event)

        self.position = start_node_id
        self._has_found_source = self.found_source_slow()
        self.moves = 0

        self._has_gui = hasattr(sim, "gui")

        if self._has_gui:
            self._draw(0, self.position)

    def _source_ids(self):
        return self._sim.metrics.source_ids

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        raise NotImplementedError()

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        pass

    def process_attacker_rcv_event(self, d_or_e, node_id, time, detail):
        # Don't want to move if the source has been found
        if self._has_found_source:
            return False

        node_id = int(node_id)

        # Don't want to process this message if we are not on the correct node
        if self.position != node_id:
            return False

        (msg_type, prox_from_id, ult_from_id, sequence_number) = detail.split(',')

        # Doesn't want to process this message if this is a message the attacker knows to ignore
        if msg_type in MESSAGES_TO_IGNORE:
            return False

        time = float(time)
        prox_from_id = int(prox_from_id)
        ult_from_id = int(ult_from_id)
        sequence_number = int(sequence_number)

        # Record the time we received this message to allow calculation
        # of the attacker receive ratio
        if msg_type == "Normal":
            self.normal_receive_time[(ult_from_id, sequence_number)] = time

        # We get called any time a message is received anywhere,
        # so first of all filter out messages being received by any node
        # other than the node the attacker is co-located with.

        # There are a number of message types an attacker will be able
        # to identify as protocol support messages. The attacker does not move
        # in response to these messages.

        should_move = self.move_predicate(time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)

        # If a tuple is returned then we are moving to a different location than the sender
        # of the message that we just received.
        if isinstance(should_move, tuple):
            (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = should_move
            should_move = True

        if should_move:
            self._move(time, prox_from_id, msg_type=msg_type)

            self.update_state(time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)

        return should_move

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

    def handle_metrics_new_source(self, ord_source):
        self._update_min_source_distance(ord_source, self._sim.node_distance_meters(self.position, ord_source))

    def _update_min_source_distance(self, ord_source, new_distance):
        if ord_source in self.min_source_distance:
            self.min_source_distance[ord_source] = min(self.min_source_distance[ord_source], new_distance)
        else:
            self.min_source_distance[ord_source] = new_distance

    def _move(self, time, node_id, msg_type=None):
        """Moved the source to a new location."""

        self.moves += 1

        if msg_type is not None:
            self.moves_in_response_to[msg_type] += 1

        ndm = self._sim.node_distance_meters
        for ord_source in self._source_ids():
            new_distance = ndm(ord_source, node_id)
            old_distance = ndm(ord_source, self.position)

            if new_distance > old_distance:
                self.steps_away[ord_source] += 1
            elif new_distance < old_distance:
                self.steps_towards[ord_source] += 1

            self._update_min_source_distance(ord_source, new_distance)

        self.position = node_id
        self._has_found_source = self.found_source_slow()

        # Update the simulator, informing them that an attacker has found the source
        self._sim.attacker_found_source |= self._has_found_source
    
        if self._has_gui:
            self._draw(time, self.position)

    def _draw(self, time, node_id):
        """Updates the attacker position on the GUI if one is present."""
        (x, y) = self._sim.gui.node_location(node_id)

        shape_id = "attacker{}".format(self.ident)

        color = '1,0,0'

        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)

        time = self._sim.sim_time()

        self._sim.gui.scene.execute(time, 'delshape("{}")'.format(shape_id))
        self._sim.gui.scene.execute(time, 'circle(%d,%d,5,ident="%s",%s)' % (x, y, shape_id, options))

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

    def setup(self, *args, **kwargs):
        super(DeafAttackerWithEvent, self).setup(*args, **kwargs)

        self._sim.tossim.register_event_callback(self._callback, self._period)

    def _callback(self, current_time):
        self._sim.tossim.register_event_callback(self._callback, current_time + self._period)

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return False

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
        self._previous_locations = deque(maxlen=memory_size)

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
        return msg_type in MESSAGES_WITHOUT_SEQUENCE_NUMBERS or \
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
        return msg_type in MESSAGES_WITHOUT_SEQUENCE_NUMBERS or \
               self._sequence_numbers.get(seqno_key, -1) < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number

class SeqNosOOOReactiveAttacker(Attacker):
    """
    This attacker can determine the source node of certain messages
    that can be sent from multiple sources.
    It is capable of moving in response to new messages when they
    are sent out-of-order.
    """
    def __init__(self):
        super(SeqNosOOOReactiveAttacker, self).__init__()
        self._sequence_numbers = set()

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type, sequence_number)
        return msg_type in MESSAGES_WITHOUT_SEQUENCE_NUMBERS or \
               seqno_key not in self._sequence_numbers

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._sequence_numbers.add((ult_from_id, msg_type, sequence_number))


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

class SingleSourceZoomingAttacker(Attacker):
    """
    This attacker can determine the source node of certain messages
    that can be sent from multiple sources. This attacker focuses
    on zooming in on one source id. If that node does not have a source
    present, then it will ignore messages from that node in the future.
    """
    def __init__(self):
        super(SingleSourceZoomingAttacker, self).__init__()
        self._sequence_numbers = {}
        self._current_node_target = None
        self._discarded_node_targets = {}

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)

        if ult_from_id in self._discarded_node_targets:
            return False

        if self._current_node_target is None:
            self._current_node_target = ult_from_id

        if self._current_node_target != ult_from_id:
            return False

        return msg_type in MESSAGES_WITHOUT_SEQUENCE_NUMBERS or \
               self._sequence_numbers.get(seqno_key, -1) < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number

        # Ignore messages from this node in the future
        if self.position == self._current_node_target and not self._has_found_source:
            self._current_node_target = None
            self._discarded_node_targets.add(self.position)


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
        return msg_type in MESSAGES_WITHOUT_SEQUENCE_NUMBERS or \
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
        self._previous_locations = []

    def _move_to_previous_location_on_timeout(self, time):
        if self._last_move_time is not None and len(self._previous_locations) > 0 and np.isclose(time, self._last_move_time + self._wait_time_secs):
            self._move(time, self._previous_locations.pop())

            self._last_move_time = time

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        return msg_type in MESSAGES_WITHOUT_SEQUENCE_NUMBERS or \
               self._sequence_numbers.get(seqno_key, -1) < sequence_number

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        seqno_key = (ult_from_id, msg_type)
        self._sequence_numbers[seqno_key] = sequence_number

        self._last_move_time = time
        self._previous_locations.append(node_id)

        self._sim.register_event_callback(self._move_to_previous_location_on_timeout, self._last_move_time + self._wait_time_secs)

    def __str__(self):
        return type(self).__name__ + "(wait_time_secs={})".format(self._wait_time_secs)

class RHMAttacker(Attacker):
    def __init__(self, clear_period, history_window_size, moves_per_period):
        super(RHMAttacker, self).__init__()

        self._clear_period = clear_period
        self._moves_per_period = moves_per_period
        self._history_window_size = history_window_size

        self._history = [None] * self._history_window_size
        self._history_index = 0

        self._messages = []
        self._num_moves = 0

        self._next_message_count_wait = None

        self._started_clear_event = False

    def setup(self, *args, **kwargs):
        super(RHMAttacker, self).setup(*args, **kwargs)

        self._set_next_message_count_wait()

    def _clear_messages(self, current_time):
        self._started_clear_event = True
        self._messages = []
        self._num_moves = 0
        self._set_next_message_count_wait()

        self._sim.register_event_callback(self._clear_messages, current_time + self._clear_period)

    def _set_next_message_count_wait(self):
        """Set the number of messages to wait for until next moving."""
        self._next_message_count_wait = self._sim.rng.randint(1, max(1, self._moves_per_period - self._num_moves))

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):

        # Start clear message event when first message is received
        if not self._started_clear_event:
            self._started_clear_event = True
            self._sim.register_event_callback(self._clear_messages, time + self._clear_period)

        self._messages.append((time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number))

        # Have made fewer moves than allowed
        can_move = self._num_moves < self._moves_per_period

        # Have we waited for enough messages
        choose_move = len(self._messages) >= self._next_message_count_wait

        if can_move and choose_move:
            filtered_message = [
                (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)
                for (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)
                in self._messages

                if prox_from_id not in self._history
            ]

            # If there are no possible moves, then do not move
            if len(filtered_message) == 0:
                return False

            # Randomly pick a previous message to follow
            return self._sim.rng.choice(filtered_message)

        return False

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        if len(self._history) > 0:
            self._history[self._history_index] = node_id
            self._history_index = (self._history_index + 1) % self._history_window_size

        self._num_moves += 1
        self._set_next_message_count_wait()

    def __str__(self):
        return type(self).__name__ + "(clear_period={},history_window_size={},moves_per_period={})".format(
            self._clear_period, self._history_window_size, self._moves_per_period)

class RHMPeriodAttacker(Attacker):
    def __init__(self, dissem_period_length, clear_periods, history_window_size, moves_per_period):
        super(RHMPeriodAttacker, self).__init__()

        self._dissem_period_length = dissem_period_length
        self._clear_periods = clear_periods
        self._moves_per_period = moves_per_period
        self._history_window_size = history_window_size

        self._history = [None] * self._history_window_size
        self._history_index = 0

        self._messages = []
        self._num_moves = 0

        self._next_message_count_wait = None

        self._during_dissem = False
        self._period_count = 0;

    def setup(self, *args, **kwargs):
        super(RHMPeriodAttacker, self).setup(*args, **kwargs)

        self._sim.register_output_handler('M-SP', self.process_start_period)

        self._set_next_message_count_wait()

    def process_start_period(self, log_type, node_id, current_time, detail):
        if self._during_dissem:
            return
        self._sim.register_event_callback(self.process_end_dissem, float(current_time) + self._dissem_period_length)
        self._during_dissem = True
        self._period_count += 1
        if self._period_count >= self._clear_periods:
            self._clear_messages()
            self._period_count = 0

    def process_end_dissem(self, current_time):
        self._during_dissem = False

    def _clear_messages(self):
        self._messages = []
        self._num_moves = 0
        self._set_next_message_count_wait()

    def _set_next_message_count_wait(self):
        """Set the number of messages to wait for until next moving."""
        self._next_message_count_wait = self._sim.rng.randint(1, max(1, self._moves_per_period - self._num_moves))

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._messages.append((time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number))

        # Have made fewer moves than allowed
        can_move = self._num_moves < self._moves_per_period

        # Have we waited for enough messages
        choose_move = len(self._messages) >= self._next_message_count_wait

        if can_move and choose_move:
            filtered_message = [
                (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)
                for (time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)
                in self._messages

                if prox_from_id not in self._history
            ]

            # If there are no possible moves, then do not move
            if len(filtered_message) == 0:
                return False

            # Randomly pick a previous message to follow
            return self._sim.rng.choice(filtered_message)

        return False

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        if len(self._history) > 0:
            self._history[self._history_index] = node_id
            self._history_index = (self._history_index + 1) % self._history_window_size

        self._num_moves += 1
        self._set_next_message_count_wait()

    def __str__(self):
        return type(self).__name__ + "(dissem_period_length={},clear_periods={},history_window_size={},moves_per_period={})".format(
            self._dissem_period_length, self._clear_periods, self._history_window_size, self._moves_per_period)

def models():
    """A list of the the available attacker models."""
    return Attacker.__subclasses__() # pylint: disable=no-member

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError("The source ({}) is not valid. (Did you forget the brackets after the name?)".format(source))

    if not isinstance(result, Attacker):
        raise RuntimeError("The source ({}) is not a valid instance of an Attacker.".format(source))

    return result
