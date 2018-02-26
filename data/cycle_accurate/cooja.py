
from datetime import datetime
import os.path

import simulator.CoojaPlatform as CoojaPlatform

def name():
    return __name__

def platform():
    """The hardware platforms of the simulator"""
    return [model().platform() for model in CoojaPlatform.models()]

def log_mode():
    return "cooja"
    #return "unbuffered_printf"

def url():
    return "http://www.contiki-os.org"

def build_arguments():
    return {
        # Cooja does its own detection of Leds being on or not
        # This detection is cheaper than using the serial output
        # on the nodes. So we disable logging Led output here.
        "SLP_USES_GUI_OUPUT": 1,
        "SLP_LEDS_RECORD_NO_SERIAL": 1,
    }

def fastserial_supported():
    return True

def create_csc(csc, target_directory, a):
    """Output simulation csc"""
    import os.path
    from xml.sax.saxutils import escape

    from simulator import Configuration

    def pcsc(*args, **kwargs):
        print(*args, file=csc, **kwargs)

    firmware_path = os.path.abspath(os.path.join(target_directory, "main.exe"))

    if not os.path.exists(firmware_path):
        raise RuntimeError(f"The firmware at {firmware_path} is missing")

    pcsc('<?xml version="1.0" encoding="UTF-8"?>')
    pcsc('<!-- Generated at: {} -->'.format(datetime.now()))
    pcsc('<simconf>')
    pcsc('  <project EXPORT="discard">[APPS_DIR]/mrm</project>')
    pcsc('  <project EXPORT="discard">[APPS_DIR]/mspsim</project>')
    pcsc('  <project EXPORT="discard">[APPS_DIR]/avrora</project>')
    pcsc('  <project EXPORT="discard">[APPS_DIR]/serial_socket</project>')
    pcsc('  <project EXPORT="discard">[APPS_DIR]/collect-view</project>')
    pcsc('  <project EXPORT="discard">[APPS_DIR]/powertracker</project>')
    pcsc('  <simulation>')
    pcsc('    <title>My simulation</title>')
    pcsc('    <randomseed>{}</randomseed>'.format(a.args.seed))
    pcsc('    <motedelay_us>{}</motedelay_us>'.format(int(a.args.latest_node_start_time * 1000000)))
    pcsc('    <radiomedium>')
    pcsc(a.args.radio_model.cooja_csc())
    pcsc('    </radiomedium>')
    pcsc('    <events>')
    pcsc('      <logoutput>40000</logoutput>')
    pcsc('    </events>')
    pcsc('    <motetype>')
    pcsc(a.args.platform.cooja_csc(firmware_path))
    pcsc('    </motetype>')

    # Output topology file
    configuration = Configuration.create(a.args.configuration, a.args)

    for (nid, (x, y)) in sorted(configuration.topology.nodes.items(), key=lambda k: k[0].nid):
        pcsc('    <mote>')
        pcsc('      <breakpoints />')
        pcsc('      <interface_config>')
        pcsc('        org.contikios.cooja.interfaces.Position')
        pcsc('        <x>{}</x>'.format(x))
        pcsc('        <y>{}</y>'.format(y))
        pcsc('        <z>0.0</z>')
        pcsc('      </interface_config>')

        pcsc(a.args.platform.node_interface_configs(nid=nid))

        pcsc('      <motetype_identifier>{}</motetype_identifier>'.format(a.args.platform.platform()))
        pcsc('    </mote>')

    pcsc('  </simulation>')

    try:
        seconds_to_run = a.args.safety_period
    except AttributeError:
        slowest_source_period = a.args.source_period if isinstance(a.args.source_period, float) else a.args.source_period.slowest()
        seconds_to_run = configuration.size() * 4.0 * slowest_source_period

    # Many algorithms have some sort of setup period, so it is important to allow cooja to consider some time for this
    # Try getting this value from the algorithm itself, otherwise guess 10 seconds
    seconds_to_run += getattr(a, "cycle_accurate_setup_period", 15.0)

    # See: https://github.com/contiki-os/contiki/wiki/Using-Cooja-Test-Scripts-to-Automate-Simulations
    # for documentation on this scripting language

    pcsc('  <plugin>')
    pcsc('    org.contikios.cooja.plugins.ScriptRunner')
    pcsc('    <plugin_config>')
    pcsc('      <script>')
    pcsc(escape(f"""
/* Make test automatically timeout after the safety period (milliseconds) */
TIMEOUT({int(seconds_to_run * 1000)}, log.testOK()); /* milliseconds. print last msg at timeout */

// Detect Leds changing on the motes
// Doing this in Cooja is cheaper than doing it on the motes
function LedObserver(node)
{{
    this.node = node;
    this.green = null;
    this.yellow = null;
    this.red = null;
    this.update = function(o, arg)
    {{
        var mmled = o;

        var g = mmled.isGreenOn() ? 1 : 0;  // Led1
        var y = mmled.isRedOn() ? 1 : 0;    // Led0
        var r = mmled.isYellowOn() ? 1 : 0; // Led2

        if (this.green != g || this.red != r || this.yellow != y)
        {{
            this.green = g;
            this.red = r;
            this.yellow = y;

            java.lang.System.err.println(sim.getSimulationTime() + "|LedsCooja:D:" + this.node.getID() + ":None:" + y + "," + g + "," + r);
        }}
    }};
}}

allMotes = sim.getMotes();
for (var i = 0; i < allMotes.length; i++)
{{
    ledObserver = new java.util.Observer(new LedObserver(allMotes[i]));

    allMotes[i].getInterfaces().getLED().addObserver(ledObserver);
}}

while (true)
{{
    java.lang.System.err.println(time + "|" + msg);

    YIELD();
}}
log.testOK(); /* Report test success and quit */
"""))
    pcsc('      </script>')
    pcsc('      <active>true</active>')
    pcsc('    </plugin_config>')
    pcsc('  </plugin>')

    pcsc('</simconf>')

def write_csc(target_directory, a):
    with open(os.path.join(target_directory, f"sim.{a.args.seed}.csc"), "w") as csc:
        create_csc(csc, target_directory, a)

def post_build_actions(target_directory, a):
    a.args.platform.post_build(target_directory, a)
