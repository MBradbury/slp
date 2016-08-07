import re

from simulator.Simulation import OutputCatcher, Simulation, OfflineSimulation

###############################################
class DebugAnalyzer:
    LED     = 0
    AM_SEND = 1
    AM_RECV = 2
    CHANGE  = 3
    DAS     = 4

    LED_RE    = re.compile(r'LEDS: Led(\d) (.*)\.')
    AMSEND_RE = re.compile(r'AM: Sending packet \(id=(\d+), len=(\d+)\) to (\d+)')
    AMRECV_RE = re.compile(r'Received active message \(0x[0-9a-f]*\) of type (\d+) and length (\d+)')
    CHANGE_RE = re.compile(r'The node has become a ([a-zA-Z]+)')

    DAS_RE    = re.compile(r'DAS is (\d)')

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
            return (self.LED, (ledno,state))

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

        # Node becoming TFS, PFS or Normal
        match = self.CHANGE_RE.match(detail)
        if match is not None:
            kind = match.group(1)
            return (self.CHANGE, (kind,))

        # Check whether DAS is broken
        match = self.DAS_RE.match(detail)
        if match is not None:
            state = int(match.group(1))
            return (self.DAS, (state,))

        return None

class Gui:
    def __init__(self, sim, node_position_scale_factor=None, node_label=None):

        from simulator.topovis.TopoVis import Scene
        from simulator.topovis.TkPlotter import Plotter

        # Setup an animating canvas
        self.scene = Scene(timescale=1)
        self.scene.addPlotter(Plotter())


        self._sim = sim

        # Default factor to scale the node positions by
        self._node_position_scale_factor = node_position_scale_factor

        # e.g. "SourceBroadcasterC.min_source_distance"
        self._node_label = node_label


        # set line style used for neighbour relationship
        self.scene.execute(0, 'linestyle(1,color=(.7,.7,.7))')

        # draw nodes on animating canvas
        for node in sim.nodes:
            self.scene.execute(0, 'node({},{},{})'.format(node.nid, *self._adjust_location(node.location)))
        

        self._debug_analyzer = DebugAnalyzer()

        # Setup a pipe for monitoring dbg messages
        self._sim.register_output_handler('LedsC', self._process_message)
        self._sim.register_output_handler('AM', self._process_message)
        self._sim.register_output_handler('Fake-Notification', self._process_message)
        self._sim.register_output_handler('Node-Change-Notification', self._process_message)
        self._sim.register_output_handler('DAS-State', self._process_message)

    def _adjust_location(self, loc):
        factor = self._node_position_scale_factor
        return (loc[0] * factor, loc[1] * factor)

    def node_location(self, node_id):
        return self._adjust_location(self._sim.nodes[node_id].location)

    ####################
    def _animate_leds(self, time, node_id, detail):
        (ledno, state) = detail
        (x, y) = self.node_location(node_id)
        shape_id = 'leds:{}:{}'.format(node_id, ledno)

        if state == 0:
            self.scene.execute(time, 'delshape("%s")' % shape_id)
            return

        if ledno == 0:
            x, y = x+5, y+5
            color = '1,0,0'
        elif ledno == 1:
            x, y = x, y+5
            color = '0,.8,0'
        elif ledno == 2:
            x, y = x-5, y+5
            color = '0,0,1'
        else:
            raise RuntimeError("Unknown led number {}".format(ledno))

        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)
        self.scene.execute(time, 'circle({},{},2,ident="{}",{})'.format(x, y, shape_id, options))

    ####################
    def _animate_am_send(self, time, sender, detail):
        (amtype, amlen, amdst) = detail
        (x, y) = self.node_location(sender)
        self.scene.execute(time)
        #self.scene.execute(time,
        #           'circle(%d,%d,%d,line=LineStyle(color=(1,0,0),dash=(1,1)),delay=.3)'
        #       % (x,y,self.wireless_range))

    ####################
    def _animate_am_receive(self, time, receiver, detail):
        (amtype, amlen) = detail
        (x, y) = self.node_location(receiver)
        self.scene.execute(time,
            'circle(%d,%d,%d,line=LineStyle(color=(0,0,1),width=3),delay=.3)'
            % (x, y, 10))

    def _animate_change_state(self, time, node, detail):
        (kind,) = detail

        pfs_colour = [x / 255.0 for x in (225, 41, 41)]
        tfs_colour = [x / 255.0 for x in (196, 196, 37)]
        tailfs_colour = [x / 255.0 for x in (196, 146, 37)]
        source_colour = [x / 255.0 for x in (64, 168, 73)]
        sink_colour = [x / 255.0 for x in (36, 160, 201)]
        normal_colour = [0, 0, 0]

        if kind in {"TFS", "TempFakeNode"}:
            colour = tfs_colour
        elif kind in {"PFS", "PermFakeNode"}:
            colour = pfs_colour
        elif kind in {"TailFS", "TailFakeNode"}:
            colour = tailfs_colour
        elif kind in {"Normal", "NormalNode"}:
            colour = normal_colour
        elif kind in {"Source", "SourceNode"}:
            colour = source_colour
        elif kind in {"Sink", "SinkNode"}:
            colour = sink_colour
        else:
            raise RuntimeError("Unknown kind '{}'".format(kind))

        self.scene.execute(time, 'nodecolor({},{},{},{})'.format(node, *colour))

    def _animate_das_state(self, time, node, detail):
        (state,) = detail
        (x,y) = self.node_location(node)
        if state == 0:
            self.scene.execute(time,
                    'circle(%d,%d,%d,line=LineStyle(color=(1,0,0),width=5),delay=.8)'
                    % (x, y, 10))

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
            DebugAnalyzer.CHANGE: self._animate_change_state,
            DebugAnalyzer.DAS: self._animate_das_state

        }[event_type](time, node_id, detail)

###############################################
class GuiSimulation(Simulation):
    def __init__(self, module_name, configuration, args):

        super(GuiSimulation, self).__init__(
            module_name=module_name,
            configuration=configuration,
            args=args,
            load_nesc_variables=True)

        self._gui = Gui(self, node_position_scale_factor=args.gui_scale, node_label=args.gui_node_label)

        if self._gui._node_label is not None:
            variables = self.nesc_app.variables.variables()[0::3]
            if self._gui._node_label not in variables:
                raise RuntimeError("The variable {} was not present in the list known to python".format(self._gui._node_label))


    def _during_run(self, event_count):
        super(GuiSimulation, self)._during_run(event_count)

        if event_count % 10 == 0 and self._gui._node_label is not None and self.nesc_app is not None:
            time = self.sim_time()

            for node in self.nodes:
                var = node.tossim_node.getVariable(self._gui._node_label)
                value = var.getData()

                if value == "<no such variable>":
                    raise RuntimeError("No variable called '{}' exists.".format(self._gui._node_label))

                self._gui.scene.execute(time, 'nodelabel({},{})'.format(node.nid, value))

###############################################

class GuiOfflineSimulation(OfflineSimulation):
    def __init__(self, module_name, configuration, args, log_filename):
        super(GuiOfflineSimulation, self).__init__(
            module_name=module_name,
            configuration=configuration,
            args=args,
            log_filename=log_filename)
        
        self._gui = Gui(self, node_position_scale_factor=args.gui_scale)
