from collections import Counter, deque
import inspect

import numpy as np

from simulator.Topology import OrderedId

from data.restricted_eval import restricted_eval

# When an attacker receives any of these messages,
# do not check the seqno just move.
MESSAGES_WITHOUT_SEQUENCE_NUMBERS = {
    'DummyNormal', 'Move', 'Beacon', 'CTPBeacon',
    'Inform', 'Search', 'Change', 'EmptyNormal', 'Poll',
    'Disable', 'Repair', 'Crash',
}

# An attacker can detect these are not messages to follow,
# so the attacker will ignore these messages.
MESSAGES_TO_IGNORE = {
    'Beacon', 'Away', 'Move', 'Choose', 'Dissem',
    'CTPBeacon', 'Inform', 'Search', 'Change',
    'Poll', 'Notify', 'Disable', 'Repair', 'Activate', 'Crash',
}

class Attacker(object):
    def __init__(self, start_location="only_sink", message_detect="using_position"):
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

        self._start_location = start_location
        self._message_detect = message_detect

        self._listen_range = None

    def build_arguments(self):
        arguments = {}

        if self._message_detect == "using_position":
            arguments["SLP_ATTACKER_USES_A_R_EVENT"] = 1

        return arguments


    def _get_starting_node_id(self):
        conf = self._sim.configuration

        if self._start_location == "only_sink":
            # The attacker should start at the location of the only sink
            # If there are more than one sink it is an error
            if len(conf.sink_ids) != 1:
                raise RuntimeError("Attacker with start_position={} does not know where to start as there is more than one sink".format(
                    self._start_location))

            attacker_start = next(iter(conf.sink_ids))

        elif self._start_location == "random_sink":
            attacker_start = self._sim.rng.choice(conf.sink_ids)

        else:
            try:
                attacker_start = conf.topology.t2o(conf.get_node_id(self._start_location))
            except:
                raise RuntimeError("Attacker with start_position={} does not know where to start as it is an unknown position".format(
                    self._start_location))

        return attacker_start

    def _register_handlers(self):
        # An attacker has multiple options as to how it detects a message.
        #
        # With "using_position" it can use the node it is co-located with
        # and when that node receives a message, then the attacker also received a message.
        # 
        # However, when duty cycling this technique is unreliable.
        # So the attacker needs to detect messages broadcasts within some range.
        if self._message_detect == "using_position":
            self._sim.register_output_handler('A-R', self.process_attacker_rcv_event)

        elif self._message_detect.startswith("within_range"):

            self._listen_range = float(self._message_detect[self._message_detect.find('(')+1:self._message_detect.find(')')])

            self._sim.register_output_handler('M-CB', self.process_attacker_neighbour_rcv_event)
            self._sim.register_output_handler('A-R', None)

        else:
            raise RuntimeError(f"Unknown message_detect option {self._message_detect}")


    def setup(self, sim, ident):
        self._sim = sim
        self.ident = ident

        self._register_handlers()

        self.position = self._get_starting_node_id()

        if __debug__:
            if not isinstance(self.position, OrderedId):
                raise TypeError("self.position must be a OrderedId but is", type(self.position))
        
        self._has_found_source = self.found_source_slow()
        self.moves = 0

        self._has_gui = hasattr(sim, "gui")

        if self._has_gui:
            self._draw(0, self.position)

        self._has_metrics_attacker_delivers = hasattr(self._sim.metrics, "_attacker_delivers")

        if self._has_metrics_attacker_delivers:
            self._sim.metrics._attacker_history[self.ident].append((0.0, self.position))

    def _source_ids(self):
        return self._sim.metrics.source_ids()

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        raise NotImplementedError()

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        pass

    def process_attacker_rcv_event(self, d_or_e, node_id, time, detail):
        # Don't want to move if the source has been found
        if self._has_found_source:
            return False

        node_id = OrderedId(int(node_id))

        # Don't want to process this message if we are not on the correct node
        if self.position != node_id:
            return False

        (msg_type, prox_from_id, ult_from_id, sequence_number, rssi, lqi) = detail.split(',')

        time = float(time)
        msg_type = self._sim.metrics.message_kind_to_string(msg_type)

        # Record when messages have been delivered when requested
        if self._has_metrics_attacker_delivers:
            self._sim.metrics._attacker_delivers.setdefault(self.ident, {}).setdefault(msg_type, []).append((time, self.position))

        # Doesn't want to process this message if this is a message the attacker knows to ignore
        if msg_type in MESSAGES_TO_IGNORE:
            return False

        prox_from_id = OrderedId(int(prox_from_id))
        ult_from_id = OrderedId(int(ult_from_id))
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
            (old_time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number) = should_move
            should_move = True

        if should_move:
            self._move(time, prox_from_id, msg_type=msg_type)

            self.update_state(time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number)

        return should_move

    def process_attacker_neighbour_rcv_event(self, d_or_e, node_id, time, detail):
        (kind, status, ultimate_source_id, sequence_number, tx_power, hex_buffer) = detail.split(',')

        # Check that the bcast was successful
        if status != "0":
            return

        ord_node_id = OrderedId(int(node_id))

        if self._sim.node_distance_meters(ord_node_id, self.position) <= self._listen_range:

            rssi = None
            lqi = None

            detail = (kind, node_id, ultimate_source_id, sequence_number, rssi, lqi)

            return self.process_attacker_rcv_event("D", self.position.nid, time, ",".join(str(x) for x in detail))

        return False


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

        if self._has_metrics_attacker_delivers:
            self._sim.metrics._attacker_history[self.ident].append((time, self.position))

    def _draw(self, time, node_id):
        """Updates the attacker position on the GUI if one is present."""
        (x, y) = self._sim.gui.node_location(node_id)

        shape_id = "attacker{}".format(self.ident)

        color = '1,0,0'

        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)

        time = self._sim.sim_time()

        self._sim.gui.scene.execute(time, 'delshape({!r})'.format(shape_id))
        self._sim.gui.scene.execute(time, 'circle({},{},5,ident={!r},{})'.format(x, y, shape_id, options))

    def _build_str(self, short=False):
        self_as = inspect.signature(self.__init__)
        attacker_as = inspect.signature(Attacker.__init__)

        # Remove the self parameter
        self_as_params = [
            name
            for (name, param) in self_as.parameters.items()
            if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD) and param.name != 'self'
        ]
        attacker_as_params = [
            name
            for (name, param) in attacker_as.parameters.items()
            if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD) and param.name != 'self'
        ]

        if short:
            params = ",".join(repr(getattr(self, "_" + name)) for name in self_as_params)
        else:
            params = ",".join("{}={!r}".format(name, getattr(self, "_" + name)) for name in self_as_params)


        base_class_defaults = {"start_location": "only_sink", "message_detect": "using_position"}

        # Only display "start_location" if it is the default value
        # This maintains compatibility with previous results files
        attacker_names = ",".join(
            "{}={!r}".format(name, getattr(self, "_" + name))
            for name in attacker_as_params
            if name not in base_class_defaults or getattr(self, f"_{name}") != base_class_defaults[name]
        )

        return "{}({})".format(type(self).__name__, ",".join(x for x in (params, attacker_names) if len(x) > 0))

    def __str__(self):
        return self._build_str(short=False)

    def short_name(self):
        return self._build_str(short=True)

class DeafAttacker(Attacker):
    """An attacker that does nothing when it receives a message"""
    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return False

class DeafAttackerWithEvent(Attacker):
    """An attacker that does nothing when it receives a message.
    This attacker also inserts a callback every period seconds."""
    def __init__(self, period, **kwargs):
        super().__init__(**kwargs)
        self._period = period

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)

        self._sim.tossim.register_event_callback(self._callback, self._period)

    def _callback(self, current_time):
        self._sim.tossim.register_event_callback(self._callback, current_time + self._period)

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return False

class BasicReactiveAttacker(Attacker):
    """An attacker that reacts to every message that it should react to."""
    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return True

class IgnorePreviousLocationReactiveAttacker(Attacker):
    """
    Same as IgnorePastNLocationsReactiveAttacker(1)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._previous_location = None

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return self._previous_location != prox_from_id

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._previous_location = node_id

class IgnorePastNLocationsReactiveAttacker(Attacker):
    def __init__(self, memory_size, **kwargs):
        super().__init__(**kwargs)
        self._memory_size = memory_size
        self._previous_locations = deque(maxlen=memory_size)

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return prox_from_id not in self._previous_locations

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._previous_locations.append(node_id)

class TimeSensitiveReactiveAttacker(Attacker):
    def __init__(self, wait_time_secs, **kwargs):
        super().__init__(**kwargs)
        self._previous_location = None
        self._last_moved_time = None
        self._wait_time_secs = wait_time_secs

    def move_predicate(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        return self._last_moved_time is None or \
               abs(time - self._last_moved_time) >= self._wait_time_secs

    def update_state(self, time, msg_type, node_id, prox_from_id, ult_from_id, sequence_number):
        self._previous_location = node_id
        self._last_moved_time = time


class SeqNoReactiveAttacker(Attacker):
    """
    This attacker can determine the type of a message and its sequence number,
    but is unaware of the ultimate source of the message.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
    def __init__(self, msg_type, **kwargs):
        super().__init__(**kwargs)
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
    def __init__(self, wait_time_secs, **kwargs):
        super().__init__(**kwargs)
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


class RHMAttacker(Attacker):
    def __init__(self, clear_period, history_window_size, moves_per_period, **kwargs):
        super().__init__(**kwargs)

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
        super().setup(*args, **kwargs)

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


class RHMPeriodAttacker(Attacker):
    def __init__(self, dissem_period_length, clear_periods, history_window_size, moves_per_period, **kwargs):
        super().__init__(**kwargs)

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
        self._period_count = 0

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)

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


def models():
    """A list of the the available attacker models."""
    return Attacker.__subclasses__() # pylint: disable=no-member

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError(f"The source ({source}) is not valid. (Did you forget the brackets after the name?)")

    if not isinstance(result, Attacker):
        raise RuntimeError(f"The source ({source}) is not a valid instance of an Attacker.")

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
