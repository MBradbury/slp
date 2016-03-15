import re

from simulator.Simulator import OutputCatcher
from simulator.Simulation import Simulation

###############################################
class DebugAnalyzer:
    LED     = 0
    AM_SEND = 1
    AM_RECV = 2
    CHANGE  = 3

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    LED_RE    = re.compile(r'LEDS: Led(\d) (.*)\.')
    AMSEND_RE = re.compile(r'AM: Sending packet \(id=(\d+), len=(\d+)\) to (\d+)')
    AMRECV_RE = re.compile(r'Received active message \(0x[0-9a-f]*\) of type (\d+) and length (\d+)')
    CHANGE_RE = re.compile(r'The node has become a ([a-zA-Z]+)')

    ####################
    def __init__(self):
        pass

    ####################
    def analyze(self, dbg):
        match = self.WHOLE_RE.match(dbg)
        if match is None:
            return None

        node_id = int(match.group(1))
        detail = match.group(2)

        # LED message
        match = self.LED_RE.match(detail)
        if match is not None:
            ledno = int(match.group(1))
            stateStr = match.group(2)
            if stateStr == 'off':
                state = 0
            else:
                state = 1
            return (node_id, self.LED, (ledno,state))

        # AM Send message
        match = self.AMSEND_RE.match(detail)
        if match is not None:
            amtype = int(match.group(1))
            amlen  = int(match.group(2))
            amdst  = int(match.group(3))
            return (node_id, self.AM_SEND, (amtype, amlen, amdst))

        # AM Receive message
        match = self.AMRECV_RE.match(detail)
        if match is not None:
            amtype = int(match.group(1))
            amlen  = int(match.group(2))
            return (node_id, self.AM_RECV, (amtype, amlen))

        # Node becoming TFS, PFS or Normal
        match = self.CHANGE_RE.match(detail)
        if match is not None:
            kind = match.group(1)
            return (node_id, self.CHANGE, (kind,))

        return None

###############################################
class GuiSimulation(Simulation):
    ####################
    def __init__(self, module_name, configuration, args):

        super(GuiSimulation, self).__init__(
            module_name=module_name,
            configuration=configuration,
            args=args,
            load_nesc_variables=True)

        self.scene = None

        # Default factor to scale the node positions by
        self._node_position_scale_factor = 6

        self._node_label = None # "SourceBroadcasterC.min_source_distance"

        self._debug_analyzer = DebugAnalyzer()

        # Setup a pipe for monitoring dbg messages
        dbg = OutputCatcher(self._process_message)
        dbg.register(self, 'LedsC')
        dbg.register(self, 'AM')
        dbg.register(self, 'Fake-Notification')
        dbg.register(self, 'Node-Change-Notification')
        self.add_output_processor(dbg)
        
    def _adjust_location(self, loc):
        factor = self._node_position_scale_factor
        return (loc[0] * factor, loc[1] * factor)

    def node_location(self, node_id):
        return self._adjust_location(self.nodes[node_id].location)

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

    ####################
    def _process_message(self, dbg):
        result = self._debug_analyzer.analyze(dbg)
        if result is None:
            return

        (node_id, event_type, detail) = result

        return {
            DebugAnalyzer.LED: self._animate_leds,
            DebugAnalyzer.AM_SEND: self._animate_am_send,
            DebugAnalyzer.AM_RECV: self._animate_am_receive,
            DebugAnalyzer.CHANGE: self._animate_change_state

        }[event_type](self.sim_time(), node_id, detail)

    ####################
    def _pre_run(self):
        super(GuiSimulation, self)._pre_run()

        from simulator.topovis.TopoVis import Scene
        from simulator.topovis.TkPlotter import Plotter

        time = self.sim_time()

        # Setup an animating canvas
        self.scene = Scene(timescale=1)
        self.scene.addPlotter(Plotter())

        # set line style used for neighbour relationship
        self.scene.execute(time, 'linestyle(1,color=(.7,.7,.7))')

        # draw nodes on animating canvas
        for node in self.nodes:
            self.scene.execute(time,
                'node({},{},{})'.format(node.nid, *self._adjust_location(node.location)))

    def _during_run(self, event_count):
        super(GuiSimulation, self)._during_run(event_count)

        if (event_count == 1 or event_count % 250 == 0) and self._node_label is not None and self.nesc_app is not None:
            for node in self.nodes:
                time = self.sim_time()

                var = node.tossim_node.getVariable(self._node_label)
                data = var.getData()

                value = data

                if value == "<no such variable>":
                    raise RuntimeError("No variable called '{}' exists.".format(self._node_label))

                self.scene.execute(time, 'nodelabel({},{})'.format(node.nid, value))

###############################################
