from __future__ import print_function, division

import re

from simulator.Simulation import Simulation, OfflineSimulation

###############################################
class DebugAnalyzer:
    LED     = 0
    AM_SEND = 1
    AM_RECV = 2
    CHANGE  = 3
    DAS     = 4
    ARROW   = 5
    AM_SNOOP = 6

    LED_RE    = re.compile(r'LEDS: Led(\d) (.*)\.')
    AMSEND_RE = re.compile(r'AM: Sending packet \(id=(\d+), len=(\d+)\) to (\d+)')
    AMRECV_RE = re.compile(r'Received active message \(0x[0-9a-f]*\) of type (\d+) and length (\d+)')
    AMSNOOP_RE = re.compile(r'Snooped on active message of type (\d+) and length (\d+) for (\d+) @ (.+)\.')
    CHANGE_RE = re.compile(r'([a-zA-Z]+Node|<unknown>),([a-zA-Z]+Node)')
    DAS_RE    = re.compile(r'DAS is (\d)')
    ARROW_RE  = re.compile(r'arrow,(\+|\-|!),(\d+),(\d+),\(([0-9\.]+),([0-9\.]+),([0-9\.]+)\)')

    ####################
    def __init__(self):
        pass

    ####################
    def analyze(self, detail):
        # LED message
        match = self.LED_RE.match(detail)
        if match is not None:
            ledno = int(match.group(1))
            stateStr = match.group(2)
            if stateStr == 'off':
                state = 0
            else:
                state = 1
            return (self.LED, (ledno, state))

        # AM Send message
        match = self.AMSEND_RE.match(detail)
        if match is not None:
            amtype = int(match.group(1))
            amlen  = int(match.group(2))
            amdst  = int(match.group(3))
            return (self.AM_SEND, (amtype, amlen, amdst))

        # AM Receive message
        match = self.AMRECV_RE.match(detail)
        if match is not None:
            amtype = int(match.group(1))
            amlen  = int(match.group(2))
            return (self.AM_RECV, (amtype, amlen))

        match = self.AMSNOOP_RE.match(detail)
        if match is not None:
            amtype = int(match.group(1))
            amlen  = int(match.group(2))
            amtarget = int(match.group(3))
            attime  = str(match.group(4))
            return (self.AM_SNOOP, (amtype, amlen, amtarget, attime))

        # Node becoming TFS, PFS, Normal, or any of the other types
        match = self.CHANGE_RE.match(detail)
        if match is not None:
            old_kind = match.group(1)
            new_kind = match.group(2)
            return (self.CHANGE, (old_kind, new_kind))

        match = self.ARROW_RE.match(detail)
        if match is not None:
            add_remove = match.group(1)
            from_id = int(match.group(2))
            to_id = int(match.group(3))
            r = float(match.group(4))
            g = float(match.group(5))
            b = float(match.group(6))
            return (self.ARROW, (add_remove, from_id, to_id, (r,g,b)))

        # Check whether DAS is broken
        match = self.DAS_RE.match(detail)
        if match is not None:
            state = int(match.group(1))
            return (self.DAS, (state,))

        print("Unable to process:", detail)

        return None

class Gui:
    def __init__(self, sim, sim_tool, node_position_scale_factor=None):

        from simulator.topovis.TopoVis import Scene
        from simulator.topovis.TkPlotter import Plotter

        # Setup an animating canvas
        self.scene = Scene(timescale=1)
        self.scene.addPlotter(Plotter())


        self._sim = sim

        # Default factor to scale the node positions by
        self._node_position_scale_factor = node_position_scale_factor

        self.scene.execute(0, "createText('events', 200, 0, text='events: 0')")

        # set line style used for neighbour relationship
        self.scene.execute(0, 'linestyle(1,color=(.7,.7,.7))')

        # draw nodes on animating canvas
        for node in sim.nodes:
            self.scene.execute(0, 'node({},{},{})'.format(node.nid, *self._adjust_location(node.location)))
        

        self._debug_analyzer = DebugAnalyzer()

        # Setup a pipe for monitoring dbg messages
        if sim_tool == "tossim":
            self._sim.register_output_handler('LedsC', self._process_message)
            self._sim.register_output_handler('AM', self._process_message)
        elif sim_tool == "avrora":
            self._sim.register_output_handler('AVRORA-TX', self._process_avrora_tx)
            self._sim.register_output_handler('AVRORA-RX', self._process_avrora_rx)

        self._sim.register_output_handler('Fake-Notification', self._process_message)
        self._sim.register_output_handler('G-NC', self._process_message)
        self._sim.register_output_handler('G-A', self._process_message)
        self._sim.register_output_handler('DAS-State', self._process_message)

    def _adjust_location(self, loc):
        initial_position = 60.0
        factor = self._node_position_scale_factor
        return (initial_position + loc[0] * factor, initial_position + loc[1] * factor)

    def node_location(self, ordered_nid):
        return self._adjust_location(self._sim.node_from_ordered_nid(ordered_nid).location)

    ####################
    def _animate_leds(self, time, node_id, detail):
        (ledno, state) = detail
        (x, y) = self.node_location(node_id)
        shape_id = 'leds:{}:{}'.format(node_id, ledno)

        if state == 0:
            self.scene.execute(time, 'delshape({!r})'.format(shape_id))
            return

        if ledno == 0:
            # Red
            x, y = x+5, y+5
            color = '1,0,0'
        elif ledno == 1:
            # Green
            x, y = x, y+5
            color = '0,1,0'
        elif ledno == 2:
            # Blue
            x, y = x-5, y+5
            color = '0,0,1'
        else:
            raise RuntimeError("Unknown led number {}".format(ledno))

        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)
        self.scene.execute(time, 'circle({},{},2,ident={!r},{})'.format(x, y, shape_id, options))

    ####################
    def _animate_am_send(self, time, sender, detail):
        (amtype, amlen, amdst) = detail
        (x, y) = self.node_location(sender)
        self.scene.execute(time,
                   'circle(%d,%d,%d,line=LineStyle(color=(1,0,0),dash=(1,1)),delay=.2)'
               % (x, y, 10))

    ####################
    def _animate_am_receive(self, time, receiver, detail):
        (amtype, amlen) = detail
        (x, y) = self.node_location(receiver)
        self.scene.execute(time,
            'circle(%d,%d,%d,line=LineStyle(color=(0,0,1),width=3),delay=.2)'
            % (x, y, 10))

    def _animate_am_snoop(self, time, snooper, detail):
        (amtype, amlen, amtarget, attime) = detail
        (x, y) = self.node_location(snooper)
        self.scene.execute(time,
            'circle(%d,%d,%d,line=LineStyle(color=(0.0,0.5,0.5),width=2),delay=.2)'
            % (x, y, 10))

    def _animate_change_state(self, time, node, detail):
        (old_kind, new_kind) = detail

        colour_map = {
            "TempFakeNode": (196, 196, 37),
            "PermFakeNode": (225, 41, 41),
            "TailFakeNode": (196, 146, 37),
            "SearchNode":   (196, 196, 37),
            "ChangeNode":   (225, 41, 41),
            "PathNode":     (196, 196, 37),
            "NormalNode":   (0, 0, 0),
            "SourceNode":   (64, 168, 73),
            "SinkNode":     (36, 160, 201),
        }

        try:
            colour = [x / 255.0 for x in colour_map[new_kind]]
        except KeyError:
            raise RuntimeError("Unknown kind '{}'".format(new_kind))

        self.scene.execute(time, 'nodecolor({},{},{},{})'.format(node, *colour))

    def _animate_arrow(self, time, node, detail):
        (add_remove, from_id, to_id, colour) = detail

        ident = "{}->{}".format(from_id, to_id)

        try:
            (x1, y1) = self.node_location(from_id)
            (x2, y2) = self.node_location(to_id)
        except RuntimeError:
            return

        if add_remove == "-":
            self.scene.execute(time, 'delshape({!r})'.format(ident))
        elif add_remove == "+":
            self.scene.execute(time,
                'line({},{},{},{},ident={!r},line=LineStyle(arrow="head", color={}))'.format(
                    x1, y1, x2, y2, ident, repr(colour))
            )
        elif add_remove == "!":
            self.scene.execute(time, 'delshape({!r})'.format(ident))
            self.scene.execute(time,
                'line({},{},{},{},ident={!r},line=LineStyle(arrow="head", color={}))'.format(
                    x1, y1, x2, y2, ident, repr(colour))
            )
        else:
            raise RuntimeError("Unknown add/remove action {}".format(add_remove))

    def _animate_das_state(self, time, node, detail):
        (state,) = detail
        (x,y) = self.node_location(node)
        if state == 0:
            self.scene.execute(time,
                'circle({},{},10,line=LineStyle(color=(1,0,0),width=5),delay=.8)'.format(x, y))

    ####################
    def _process_message(self, d_or_e, node_id, time, without_dbg):
        result = self._debug_analyzer.analyze(without_dbg)
        if result is None:
            return

        (event_type, detail) = result

        node_id = int(node_id)

        # WARNING:
        # Here we override the time given to us by the event!
        # This is because we can get earlier events from different nodes, eg:
        #
        # Node 1, time 5
        # Node 1, time 6
        # Node 2, time 5
        # Node 1, time 7
        #
        # Overriding the time forces the time that is used to be
        # the time at the end of the events.
        time = self._sim.sim_time()

        return {
            DebugAnalyzer.LED: self._animate_leds,
            DebugAnalyzer.AM_SEND: self._animate_am_send,
            DebugAnalyzer.AM_RECV: self._animate_am_receive,
            DebugAnalyzer.AM_SNOOP: self._animate_am_snoop,
            DebugAnalyzer.CHANGE: self._animate_change_state,
            DebugAnalyzer.DAS: self._animate_das_state,
            DebugAnalyzer.ARROW: self._animate_arrow,

        }[event_type](time, node_id, detail)

    def _process_avrora_tx(self, d_or_e, node_id, time, without_dbg):
        radio_bytes, radio_time = without_dbg.split(',')

        node_id = int(node_id)

        radio_bytes = bytearray.fromhex(radio_bytes.replace(".", " "))
        radio_time = float(radio_time)

        # (amtype, amlen, amdst)
        detail = (None, len(radio_bytes), None)

        return self._animate_am_send(time, node_id, detail)

    def _process_avrora_rx(self, d_or_e, node_id, time, without_dbg):
        radio_bytes, radio_time = without_dbg.split(',')

        node_id = int(node_id)

        radio_bytes = bytearray.fromhex(radio_bytes.replace(".", " "))
        radio_time = float(radio_time)

        # (amtype, amlen)
        detail = (None, len(radio_bytes))

        return self._animate_am_receive(time, node_id, detail)

###############################################
class GuiSimulation(Simulation):
    def __init__(self, module_name, configuration, args):
        super(GuiSimulation, self).__init__(
            module_name=module_name,
            configuration=configuration,
            args=args,
            load_nesc_variables=True)

        self._node_label = args.gui_node_label

        self.gui = Gui(self, args.sim, node_position_scale_factor=args.gui_scale)

        if self._node_label is not None:
            variables = self.nesc_app.variables.variables()
            if self._node_label not in variables:
                raise RuntimeError("The variable {} was not present in the list known to python {}".format(self._node_label, variables))


    def _during_run(self, event_count):
        if event_count % 10 == 0:
            time = self.sim_time()

            self.gui.scene.execute(time, "updateText('events', text='events: {}')".format(event_count))

            if self._node_label is not None and self.nesc_app is not None:
                for node in self.nodes:
                    var = node.tossim_node.getVariable(self._node_label)
                    value = var.getData()

                    self.gui.scene.execute(time, 'nodelabel({},{})'.format(node.nid, value))

###############################################

class GuiOfflineSimulation(OfflineSimulation):
    def __init__(self, module_name, configuration, args, event_log):
        super(GuiOfflineSimulation, self).__init__(
            module_name=module_name,
            configuration=configuration,
            args=args,
            event_log=event_log)
        
        self.gui = Gui(self, args.sim, node_position_scale_factor=args.gui_scale)
