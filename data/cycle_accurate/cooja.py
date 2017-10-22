from __future__ import print_function

import simulator.CoojaPlatform as CoojaPlatform

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return [model().platform() for model in CoojaPlatform.models()]

def log_mode():
    # Avrora has a special log mode that involves
    # storing the address of the buffer to be printed
    # in a variable that is watched by avrora.
    # When that variable is changed, the address of the
    # buffer it contains will be printed.
    return "unbuffered_printf"

def url():
    return "http://www.contiki-os.org"

def build_arguments():
    return {}

def fastserial_supported():
    return True

def create_csc(csc, target_directory, a):
    """Output simulation csc"""

    from simulator import Configuration

    def pcsc(*args, **kwargs):
        print(*args, file=csc, **kwargs)

    pcsc('<?xml version="1.0" encoding="UTF-8"?>')
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
    pcsc(a.args.platform.cooja_csc())
    pcsc('      <firmware EXPORT="copy">{}/main.exe</firmware>'.format(target_directory))
    pcsc('    </motetype>')

    # Output topology file
    configuration = Configuration.create(a.args.configuration, a.args)

    for (nid, (x, y)) in sorted(configuration.topology.nodes.items(), key=lambda k: k[0]):
        pcsc('    <mote>')
        pcsc('      <breakpoints />')
        pcsc('      <interface_config>')
        pcsc('        org.contikios.cooja.interfaces.Position')
        pcsc('        <x>{}</x>'.format(x))
        pcsc('        <y>{}</y>'.format(y))
        pcsc('        <z>0.0</z>')
        pcsc('      </interface_config>')
        pcsc('      <interface_config>')
        pcsc('        org.contikios.cooja.mspmote.interfaces.MspClock')
        pcsc('        <deviation>1.0</deviation>')
        pcsc('      </interface_config>')
        pcsc('      <interface_config>')
        pcsc('        org.contikios.cooja.mspmote.interfaces.MspMoteID')
        pcsc('        <id>{}</id>'.format(nid))
        pcsc('      </interface_config>')
        pcsc('      <motetype_identifier>{}</motetype_identifier>'.format(a.args.platform.platform()))
        pcsc('    </mote>')

    pcsc('  </simulation>')

    try:
        seconds_to_run = a.args.safety_period
    except AttributeError:
        slowest_source_period = a.args.source_period if isinstance(a.args.source_period, float) else a.args.source_period.slowest()
        seconds_to_run = configuration.size() * 4.0 * slowest_source_period

    # See: https://github.com/contiki-os/contiki/wiki/Using-Cooja-Test-Scripts-to-Automate-Simulations
    # for documentation on this scripting language

    pcsc('  <plugin>')
    pcsc('    org.contikios.cooja.plugins.ScriptRunner')
    pcsc('    <plugin_config>')
    pcsc('      <script>')
    pcsc("""
/* Make test automatically timeout after the safety period (milliseconds) */
TIMEOUT({milliseconds_to_run}, log.log("last msg: " + msg + "\\n")); /* milliseconds. print last msg at timeout */

while (true)
{{
    YIELD();

    java.lang.System.err.println(time + "|" + msg);
}}
log.testOK(); /* Report test success and quit */
""".format(
        milliseconds_to_run=int(seconds_to_run * 1000),
))
    pcsc('      </script>')
    pcsc('      <active>true</active>')
    pcsc('    </plugin_config>')
    pcsc('  </plugin>')

    pcsc('</simconf>')



def post_build_actions(target_directory, a):
    import os.path

    with open(os.path.join(target_directory, "sim.csc"), "w") as csc:
        create_csc(csc, target_directory, a)
