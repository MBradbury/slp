from time import sleep, time as systime
from functools import wraps
from threading import Timer
from heapq import heappush, heappop

from simulator.topovis.common import INF, DEFAULT, Color, Parameters

###############################################
class LineStyle(object):
    """
    Define a set of attributes for line drawing.  Attributes currently
    supported are
        - color: specifies color in (r,g,b) tuple, where 0 <= r,g,b <= 1
        - dash:  can be either one of the following formats, (), (s,),
          (s1,s2).  The first one results in a solid line; the second results
          in a line drawn with the length of s and skip for the same amount;
          the last will draw the line for the length of s1 and skip for s2.
          However, the actual behavior depends on the plotter.
        - width: speficies the width of the line
        - arrow: specifies how arrow heads are drawn.  Acceptable values are
          'head', 'tail', 'both', and 'none'.
    """
    def __init__(self, **kwargs):
        self.color = (0, 0, 0)
        self.dash = ()
        self.width = 1
        self.arrow = 'none'
        for (k, v) in kwargs.items():
            if k in ('color', 'dash', 'width', 'arrow'):
                setattr(self, k, v)
            else:
                raise RuntimeError('Unknown option "%s"' % k)

    def __repr__(self):
        return '[color=%s,dash=%s,width=%s,arrow=%s]' % (
            self.color, self.dash, self.width, self.arrow)

###############################################
class FillStyle(object):
    """
    Define a set of attributes for shape filling.  The only attribute currently
    supported is 'color', which specifies color in (r,g,b) tuple, where 0 <=
    r,g,b <= 1
    """
    def __init__(self, **kwargs):
        self.color = None
        for (k, v) in kwargs.items():
            if k in ['color']:
                setattr(self, k, v)
            else:
                raise RuntimeError('Unknown option "%s"' % k)

    def __repr__(self):
        return '[color=%s]' % self.color

###############################################
class TextStyle(object):
    """
    Define a set of attributes for text rendering.  Attributes currently
    supported are 'color', 'font', and 'size'.
    """
    def __init__(self, **kwargs):
        self.color = (0, 0, 0)
        for (k,v) in kwargs.items():
            if k in ['color', 'font', 'size']:
                setattr(self, k, v)
            else:
                raise RuntimeError('Unknown option "%s"' % k)

###############################################
class Node:
    """
    Define a dummy node structure to keep track of arbitrary node attributes
    """
    def __init__(self):
        pass

###############################################
class GenericPlotter:
    """
    Define a generic plotter class from which actual plotters are derived
    """
    def __init__(self, params=None):
        if params is None:
            params = Parameters()
        self.params = params
        self.scene  = None

    ###################
    def setScene(self, scene):
        self.scene = scene

    #######################################################
    # The following methods are supposed to be overridden
    #######################################################
    def init(self, tx, ty):
        pass
    def setTime(self, time):
        pass
    def node(self, ident, x, y):
        pass
    def nodemove(self, ident, x, y):
        pass
    def nodehollow(self, ident, flag):
        pass
    def nodedouble(self, ident, flag):
        pass
    def nodecolor(self, ident, r, g, b):
        pass
    def nodewidth(self, ident, width):
        pass
    def nodelabel(self, ident, label):
        pass
    def nodescale(self, ident, scale):
        pass
    def addlink(self, src, dst, style):
        pass
    def dellink(self, src, dst, style):
        pass
    def clearlinks(self):
        pass
    def show(self):
        pass
    def circle(self, x, y, r, ident, linestyle, fillstyle):
        pass
    def line(self, x1, y1, x2, y2, ident, linestyle):
        pass
    def rect(self, x1, y1, x2, y2, ident, linestyle, fillstyle):
        pass
    def delshape(self, ident):
        pass
    def linestyle(self, ident, **kwargs):
        pass
    def fillstyle(self, ident, **kwargs):
        pass
    def textstyle(self, ident, **kwargs):
        pass
    def createText(self, ident, *args, **kwargs):
        pass
    def updateText(self, ident, text):
        pass

###############################################
def informPlotters(fn):
    """
    Invoke the instance method of the same name inside each of the registered
    plotters 
    """

    # Wraps makes sure that the name and docstring of the wrapped function
    # are correctly maintained. However, information on argument names will be lost.
    @wraps(fn)
    def wrap(self, *args, **kwargs):
        fn(self, *args, **kwargs)
        for plotter in self.plotters:
            plotter_func = getattr(plotter, fn.__name__)
            plotter_func(*args, **kwargs)

    return wrap

###############################################
class Scene:
    """
    Define a scene that keeps track of every object in the model.  It also
    triggers registered plotters whenever there is a state change.
    """

    ###################
    def __init__(self,timescale=1,realtime=False):
        """
        Instantiate a Scene object.  The timescale parameter indicates how
        TopoVis should adjust time delay as specified with a scene scripting
        command.  When the realtime parameter is True, the timescale parameter
        is ignored and each scene scripting command will take effect
        immediately once invoked.
        """
        self.plotters = []
        self.time = 0.0
        self.initialized = False
        self.timescale = timescale
        self.realtime = realtime
        self.evq = []        # Event queue
        self.uniqueId = 0    # Counter for generating unique IDs

        self.dim = (0, 0)     # Terrain dimension
        self.nodes = {}      # Nodes' information
        self.links = set()   # Set of links between nodes
        self.lineStyles = {} # List of defined line styles
        self.fillStyles = {} # List of defined fill styles
        self.textStyles = {} # List of defined text styles

        if realtime:
            self.startTime = systime()


    ###################
    def setTiming(self, scale=1, realtime=False):
        self.timescale = scale
        self.realtime = realtime
        if realtime:
            self.startTime = systime() - self.time

    ###################
    def _getUniqueId(self):
        """
        Create and return a unique integer everytime it gets called
        """
        self.uniqueId = self.uniqueId + 1
        return "_" + str(self.uniqueId)

    ###################
    def addPlotter(self, plotter):
        """
        Add a plotter which accepts and visualizes scene scripts
        """
        plotter.setScene(self)
        self.plotters.append(plotter)

    ###################
    def removePlotter(self, plotter):
        """
        Remove the specified plotter from keeping track of scene scripts
        """
        self.plotters.remove(plotter)

    ###################
    def execute(self, time, cmd=None, *args, **kwargs):
        """
        Execute the scene scripting command, cmd, with specified
        variable-length and keyword arguments
        """
        if self.realtime:
            self.setTime(systime() - self.startTime)
        else:
            # examine the event queue and execute everything prior to
            # the 'current time'
            while len(self.evq) > 0 and self.evq[0][0] < time:
                (t, proc, a, kw) = heappop(self.evq)
                self.setTime(t)
                proc(*a, **kw)
            self.setTime(time)

        if cmd is None:
            return
        elif isinstance(cmd, str):
            exec('self.' + cmd)
        else:
            cmd(*args, **kwargs)

    ###################
    def executeAfter(self, delay, cmd, *args, **kwargs):
        """
        (Use internally) Wait until the specified delay, then executed the given
        command
        """
        if delay is INF:
            # no need to schedule any execution at time infinity
            return
        if self.realtime:
            def execfn():
                self.execute(0, cmd, *args, **kwargs)
                #heappush(self.evq, (0, cmd, args, kwargs)) # Probably fixes this, but also introduces a race condition
            Timer(delay, execfn).start()
        else:
            heappush(self.evq, (self.time+delay, cmd, args, kwargs))

    ###################
    def setTime(self, time):
        """
        Set the current time being tracked by TopoVis to the specified time.
        A corresponding amount of delay will be applied unless TopoVis scene
        was instantiated to run in real-time.  This method also informs all
        registered plotters about the updated time so that a label or window
        title can be updated accordingly.
        """
        if time is None:
            return

        if time < self.time:
            raise RuntimeError(f'Time cannot flow backward: current = {self.time}, new = {time}')

        if not self.realtime:
            sleep((time-self.time) * self.timescale)
            self.time = time

        for plotter in self.plotters:
            plotter.setTime(time)

    ###################
    @informPlotters
    def init(self, tx, ty):
        """
        (Scene scripting command) Intialize the scene.  This command should
        be called before any other scripting commands.
        """
        if self.initialized:
            raise RuntimeError('init() has already been called')
        self.dim = (tx, ty)
        self.initialized = True


    #########################################################################
    # All methods below define Scene Scripting Commands.  These commands also
    # inform all registered plotters to update visualization of the current
    # scene
    #########################################################################

    ###################
    @informPlotters
    def node(self, ident, x, y):
        """
        (Scene scripting command)
        Define a node with the specified ID and location (x,y)
        """
        self.nodes[ident]        = Node()
        self.nodes[ident].id     = ident
        self.nodes[ident].pos    = (x,y)
        self.nodes[ident].scale  = 1.0
        self.nodes[ident].label  = str(ident)
        self.nodes[ident].hollow = DEFAULT
        self.nodes[ident].double = DEFAULT
        self.nodes[ident].width  = DEFAULT
        self.nodes[ident].color  = DEFAULT

    ###################
    @informPlotters
    def nodemove(self, ident, x, y):
        """
        (Scene scripting command)
        Move a node whose ID is ident to a new location (x, y)
        """
        self.nodes[ident].pos = (x, y)

    ###################
    @informPlotters
    def nodecolor(self, ident, r, g, b):
        """
        (Scene scripting command)
        Set color (in rgb format, 0 <= r,g,b <= 1) of the node, specified by
        ident
        """
        self.nodes[ident].color = (r, g, b)

    ###################
    @informPlotters
    def nodelabel(self, ident, label):
        """
        (Scene scripting command)
        Set string label for the node, specified by ident
        """
        self.nodes[ident].label = label

    ###################
    @informPlotters
    def nodescale(self, ident, scale):
        """
        (Scene scripting command)
        Set node scaling factor.  By default, nodes are visualized with
        scale=1
        """
        self.nodes[ident].scale = scale

    ###################
    @informPlotters
    def nodehollow(self, ident, flag):
        """
        (Scene scripting command)
        Set node's hollow display
        """
        self.nodes[ident].hollow = flag

    ###################
    @informPlotters
    def nodedouble(self, ident, flag):
        """
        (Scene scripting command)
        Set node's double-outline display
        """
        self.nodes[ident].double = flag

    ###################
    @informPlotters
    def nodewidth(self, ident, width):
        """
        (Scene scripting command)
        Set node's outline width
        """
        self.nodes[ident].width = width

    ###################
    @informPlotters
    def addlink(self, src, dst, style):
        """
        (Scene scripting command)
        Add a link with the specified style, which is an instance of
        LineStyle, between a pair of nodes
        """
        self.links.add((src, dst, style))

    ###################
    @informPlotters
    def dellink(self, src, dst, style):
        """
        (Scene scripting command)
        Remove a link with the specified style from a pair of nodes
        """
        self.links.remove((src, dst, style))

    ###################
    @informPlotters
    def clearlinks(self):
        """
        (Scene scripting command)
        Delete all links previously added
        """
        self.links.clear()

    ###################
    @informPlotters
    def show(self):
        """
        (Scene scripting command)
        Force update of topology view
        """
        pass

    ###################
    def circle(self, x, y, r, ident=None, line=LineStyle(), fill=FillStyle(), delay=INF):
        """
        (Scene scripting command)
        Draw/update a circle centered at (x,y) with radius r.  line and fill
        are applied to the drawn object.  The object will remain on the scene
        for the specified delay.
        """
        # resolve ident and inform plotters manually
        # XXX will try to use decorator later on
        if ident is None:
            ident = self._getUniqueId()
        for plotter in self.plotters:
            plotter.circle(x, y, r, ident, line, fill)
        self.executeAfter(delay, self.delshape, ident)

    ###################
    def line(self, x1, y1, x2, y2, ident=None, line=LineStyle(), delay=INF):
        """
        (Scene scripting command)
        Draw/update a line from (x1,y1) to (x2,y2).  line and fill
        are applied to the drawn object.  The object will remain on the scene
        for the specified delay.

        """
        # resolve ident and inform plotters manually
        # XXX will try to use decorator later on
        if ident is None:
            ident = self._getUniqueId()
        for plotter in self.plotters:
            plotter.line(x1, y1, x2, y2, ident, line)
        self.executeAfter(delay, self.delshape, ident)

    ###################
    def rect(self, x1, y1, x2, y2, ident=None, line=LineStyle(), fill=FillStyle(), delay=INF):
        """
        (Scene scripting command)
        Draw/update a rectangle from (x1,y1) to (x2,y2).  line and fill
        are applied to the drawn object.  The object will remain on the scene
        for the specified delay.

        """
        # resolve ident and inform plotters manually
        # XXX will try to use decorator later on
        if ident is None:
            ident = self._getUniqueId()
        for plotter in self.plotters:
            plotter.rect(x1, y1, x2, y2, ident, line, fill)
        self.executeAfter(delay, self.delshape, ident)

    ###################
    @informPlotters
    def delshape(self, ident):
        """
        (Scene scripting command)
        Delete an animated shape (e.g., line, circle) previously created with ID ident
        """
        pass

    ###################
    @informPlotters
    def linestyle(self, ident, **kwargs):
        """
        (Scene scripting command)
        Define or redefine a line style.
        """
        self.lineStyles[ident] = LineStyle(**kwargs)

    ###################
    @informPlotters
    def fillstyle(self, ident, **kwargs):
        """
        (Scene scripting command)
        Define or redefine a fill style
        """
        self.fillStyles[ident] = FillStyle(**kwargs)

    ###################
    @informPlotters
    def textstyle(self, ident, **kwargs):
        """
        (Scene scripting command)
        Define or redefine a text style
        """
        self.textStyles[ident] = FillStyle(**kwargs)

    ###################
    @informPlotters
    def createText(self, ident, *args, **kwargs):
        pass

    ###################
    @informPlotters
    def updateText(self, ident, text):
        pass

