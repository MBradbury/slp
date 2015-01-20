import re

from Simulator import Simulator, OutputCatcher

###############################################
class DebugAnalyzer:
    LED     = 0
    AM_SEND = 1
    AM_RECV = 2
    FAKE    = 3

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    LED_RE    = re.compile(r'LEDS: Led(\d) (.*)\.')
    AMSEND_RE = re.compile(r'AM: Sending packet \(id=(\d+), len=(\d+)\) to (\d+)')
    AMRECV_RE = re.compile(r'Received active message \(0x[0-9a-f]*\) of type (\d+) and length (\d+)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+)')

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
            return (node_id, self.AM_SEND, (amtype,amlen,amdst))

        # AM Receive message
        match = self.AMRECV_RE.match(detail)
        if match is not None:
            amtype = int(match.group(1))
            amlen  = int(match.group(2))
            return (node_id, self.AM_RECV, (amtype,amlen))

        # Node becoming TFS, PFS or Normal
        match = self.FAKE_RE.match(detail)
        if match is not None:
            kind = match.group(1)
            return (node_id, self.FAKE, (kind,))

        return None

###############################################
class TosVis(Simulator):
    ####################
    def __init__(self, TOSSIM, node_locations, wireless_range, seed=None):

        super(TosVis, self).__init__(
            TOSSIM,
            node_locations=node_locations,
            wireless_range=wireless_range,
            seed=seed)

        self.run_gui = False

    def setup_gui(self):

        if self.run_gui:
            return

        self.run_gui = True

        self.debug_analyzer = DebugAnalyzer()

        # setup a pipe for monitoring dbg messages
        dbg = OutputCatcher(self._process_message)
        self.tossim.addChannel('LedsC', dbg.write)
        self.tossim.addChannel('AM', dbg.write)
        self.tossim.addChannel('Fake-Notification', dbg.write)

        self.add_output_processor(dbg)

    @staticmethod
    def adjust_location(loc):
        factor = 5
        return (loc[0] * factor, loc[1] * factor)

    def node_location(self, node_id):
        return self.adjust_location(self.nodes[node_id].location)

    ####################
    def _animate_leds(self, time, node_id, detail):
        (ledno, state) = detail
        scene = self.scene
        (x, y) = self.node_location(node_id)
        shape_id = '{}:{}'.format(node_id, ledno)

        if state == 0:
            scene.execute(time, 'delshape("%s")' % shape_id)
            return

        if ledno == 0:
            x, y = x+5, y+5
            color = '1,0,0'
        elif ledno == 1:
            x, y = x, y+5
            color = '0,.8,0'
        else:
            x, y = x-5, y+5
            color = '0,0,1'
        options = 'line=LineStyle(color=({0})),fill=FillStyle(color=({0}))'.format(color)
        scene.execute(time, 'circle({},{},2,id="{}",{})'.format(x, y, shape_id, options))

    ####################
    def _animate_am_send(self, time, sender, detail):
        (amtype, amlen, amdst) = detail
        scene = self.scene
        (x, y) = self.node_location(sender)
        scene.execute(time)
        #scene.execute(time,
        #           'circle(%d,%d,%d,line=LineStyle(color=(1,0,0),dash=(1,1)),delay=.3)'
        #       % (x,y,self.range))

    ####################
    def _animate_am_receive(self, time, receiver, detail):
        (amtype, amlen) = detail
        scene = self.scene
        (x,y) = self.node_location(receiver)
        scene.execute(time,
                'circle(%d,%d,%d,line=LineStyle(color=(0,0,1),width=3),delay=.3)'
                % (x,y,10))

    def _animate_fake_state(self, time, node, detail):
        (kind,) = detail

        pfs_colour = [x / 255.0 for x in (225,41,41)]
        tfs_colour = [x / 255.0 for x in (196,196,37)]
        normal_colour = [0,0,0]

        if kind == "TFS":
            colour = tfs_colour
        elif kind == "PFS":
            colour = pfs_colour
        elif kind == "Normal":
            colour = normal_colour
        else:
            raise RuntimeError("Unknown kind {}".format(kind))

        scene = self.scene
        scene.execute(time,
                'nodecolor({},{},{},{})'.format(*([node] + colour)))

    ####################
    def _process_message(self, dbg):
        result = self.debug_analyzer.analyze(dbg)
        if result is None:
            return

        (node_id, event_type, detail) = result

        return {
            DebugAnalyzer.LED: self._animate_leds,
            DebugAnalyzer.AM_SEND: self._animate_am_send,
            DebugAnalyzer.AM_RECV: self._animate_am_receive,
            DebugAnalyzer.FAKE: self._animate_fake_state

        }[event_type](self.sim_time(), node_id, detail)

    ####################
    def _pre_run(self):
        super(TosVis, self)._pre_run()

        if self.run_gui:
            from simulator.topovis.TopoVis import Scene
            from simulator.topovis.TkPlotter import Plotter

            # Setup an animating canvas
            self.scene = Scene(timescale=1)
            self.tkplot = Plotter()
            self.scene.addPlotter(self.tkplot)

            # set line style used for neighbor relationship
            self.scene.execute(0, 'linestyle(1,color=(.7,.7,.7))')

            # draw nodes on animating canvas
            for node in self.nodes:
                self.scene.execute(0, 'node(%d,%f,%f)' % ((node.id,) + self.adjust_location(node.location)))

###############################################
