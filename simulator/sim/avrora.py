from __future__ import print_function, division

import base64
from collections import namedtuple
import pickle
import re
import sys

try:
    import subprocess32 as subprocess
except ImportError:
    import subprocess

def parsers():
    raw_single_common = ["verbose", "seed", "configuration", "network size", "distance",
                         "node id order", "safety period",
                         "low powered listening",
                         "max buffer size"]

    return [
        ("SINGLE", None, raw_single_common + ["attacker model"]),
        ("RAW", None, raw_single_common),
        ("GUI", "SINGLE", ["gui scale"]),
        #("PARALLEL", "SINGLE", ["job size", "thread count"]),
        #("CLUSTER", "PARALLEL", ["job id"]),
    ]

def build(module, a):
    import data.cycle_accurate
    from data.run.driver.cycle_accurate_builder import Runner as Builder

    from data import submodule_loader

    target = module.replace(".", "/") + ".txt"

    avrora = submodule_loader.load(data.cycle_accurate, "avrora")

    builder = Builder(avrora, max_buffer_size=a.args.max_buffer_size)
    builder.total_job_size = 1
    
    #(a, module, module_path, target_directory)
    builder.add_job((module, a), target)

def print_version():
    import simulator.VersionDetection as VersionDetection

    print("@version:tinyos={}".format(VersionDetection.tinyos_version()))
    print("@version:avrora={}".format(VersionDetection.avrora_version()))

    print("@version:java={}".format(VersionDetection.java_version()))

def avrora_command(module, a, configuration):
    import os

    try:
        avrora_path = os.environ["AVRORA_JAR_PATH"]
    except KeyError:
        raise RuntimeError("Unable to find the environment variable AVRORA_JAR_PATH so cannot run avrora.")

    target_directory = module.replace(".", "/")

    try:
        seconds_to_run = a.args.safety_period
    except AttributeError:
        slowest_source_period = a.args.source_period if isinstance(a.args.source_period, float) else a.args.source_period.slowest()
        seconds_to_run = configuration.size() * 4.0 * slowest_source_period

    # See: http://compilers.cs.ucla.edu/avrora/help/sensor-network.html
    options = {
        "platform": "micaz",
        "simulation": "sensor-network",
        "seconds": seconds_to_run,
        "monitors": "packet,c-print,energy",
        "radio-range": a.args.distance + 0.1,
        "nodecount": str(configuration.size()),
        "topology": "static",
        "topology-file": os.path.join(target_directory, "topology.txt"),
        "random-seed": a.args.seed,

        # Needed to be able to print simdbg strings longer than 30 bytes
        "max": a.args.max_buffer_size,

        # Show the messages sent and received
        "show-packets": "true",

        # Need to disable the simulator showing colors
        "colors": "false",

        # Report time in seconds and not cycles
        # Only need a precision of 6 as python cannot handle more than that
        "report-seconds": "true",
        "seconds-precision": "6"
    }

    target_file = os.path.join(target_directory, "main.elf")

    options_string = " ".join("-{}={}".format(k,v) for (k,v) in options.items())

    # Avrora is a bit crazy as it uses a one thread per node architecture
    # This is a problem when running on a cluster as we need a way to limit the number of cores being used.

    # For the time being we just use a niceness to prevent a system from freezing.

    # Give a niceness to allow system to continue to respond
    command = "nice -15 java -jar {} {} {}".format(avrora_path, options_string, target_file)

    return command

def avrora_iter(iterable):
    from datetime import datetime

    results_start = "------------------------------------------------------------------------------"
    results_end = "=============================================================================="
    packet_stats_start = "=={ Packet monitor results }=================================================="
    energy_stats_start = "=={ Energy consumption results for node"

    RESULT_LINE_RE = re.compile(r'\s*(\d+)\s*(\d+:\d+:\d+\.\d+)\s*(.+)\s*')
    TX_LINE_RE = re.compile(r'---->\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')
    RX_LINE_RE = re.compile(r'<====\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')

    SIMULATED_TIME_RE = re.compile(r'Simulated time: (\d+) cycles\s*')
    PACKET_STATS_RE = re.compile(r'\s*(\d+)\s*(\d+) / (\d+)\s*(\d+) / (\d+)\s*(\d+)\s*(\d+)\s*')

    started = False
    ended = False

    avrora_sim_cycles = False
    avrora_tx_rt_stats = None
    avrora_energy_stats = None

    energy_stats_buffer = []

    for line in iterable:
        line = line.rstrip()

        if not started:
            # Check that the binary was loaded okay
            if line.startswith("Loading") and not line.endswith("OK"):
                raise RuntimeError(line)

            if line.startswith(results_start):
                started = True

            continue

        if started and not ended and line.startswith(results_end):
            ended = True
            continue

        if not ended:
            match = RESULT_LINE_RE.match(line)

            node = int(match.group(1))
            node_time = datetime.strptime(match.group(2)[:-3], "%H:%M:%S.%f")

            log = match.group(3)

            stime_str = node_time.strftime("%Y/%m/%d %H:%M:%S.%f")

            if log.startswith("---->"):
                tx_match = TX_LINE_RE.match(log)
                data = tx_match.group(1)
                time_length_ms = float(tx_match.group(2))

                fullstr = "{}|AVRORA-TX:D:{}:None:{},{}".format(stime_str, node, data, time_length_ms)

            elif log.startswith("<===="):
                rx_match = RX_LINE_RE.match(log)
                data = rx_match.group(1)
                time_length_ms = float(rx_match.group(2))

                fullstr = "{}|AVRORA-RX:D:{}:None:{},{}".format(stime_str, node, data, time_length_ms)

            else:
                fullstr = "{}|{}".format(stime_str, log)

            print(fullstr)

            yield fullstr

        else:
            # After the end the simulation has finished and avrora metrics are being printed
            # We need to capture, parser and convert these

            if not avrora_sim_cycles:
                match = SIMULATED_TIME_RE.match(line)
                sim_time_cycles = match.group(1)

                yield "None|AVRORA-SIM-CYCLES:D:None:None:{}".format(sim_time_cycles)

                avrora_sim_cycles = True

            if avrora_tx_rt_stats is None and line == packet_stats_start:
                avrora_tx_rt_stats = True
                continue

            if avrora_tx_rt_stats:
                if line == "":
                    avrora_tx_rt_stats = False
                    continue

                match = PACKET_STATS_RE.match(line)
                if match is None:
                    continue

                yield "None|AVRORA-PACKET-SUMMARY:D:{}:None:{}".format(
                    match.group(1),
                    ",".join(match.group(x) for x in range(2, 8))
                )

            if avrora_energy_stats is None and line.startswith(energy_stats_start):
                avrora_energy_stats = True

            if avrora_energy_stats:
                if line.startswith(energy_stats_start):

                    if len(energy_stats_buffer) > 0:
                        energy = NodeEnergy("\n".join(energy_stats_buffer))

                        yield "None|AVRORA-ENERGY-STATS:D:{}:None:{}".format(energy.nid, energy.encode())

                    energy_stats_buffer = [line]

                else:
                    energy_stats_buffer.append(line)

    if len(energy_stats_buffer) > 0:
        energy = NodeEnergy("\n".join(energy_stats_buffer))

        yield "None|AVRORA-ENERGY-STATS:D:{}:None:{}".format(energy.nid, energy.encode())


def run_simulation(module, a, count=1, print_warnings=False):
    import shlex

    from simulator import Configuration

    configuration = Configuration.create(a.args.configuration, a.args)

    command = avrora_command(module, a, configuration)

    print("@command:{}".format(command))
    sys.stdout.flush()

    command = shlex.split(command)    

    if a.args.mode == "RAW":
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)

        proc_iter = iter(proc.stdout.readline, '')

        for line in avrora_iter(proc_iter):
            print(line)

        proc.stdout.close()

        return_code = proc.wait()

        if return_code:
            raise subprocess.CalledProcessError(return_code, command)

    else:
        import copy

        if a.args.mode == "SINGLE":
            from simulator.Simulation import OfflineSimulation
        elif a.args.mode == "GUI":
            from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
        else:
            raise RuntimeError("Unknown mode {}".format(a.args.mode))

        proc = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)

        proc_iter = iter(proc.stdout.readline, '')

        with OfflineSimulation(module, configuration, a.args, event_log=avrora_iter(proc_iter)) as sim:
            # Create a copy of the provided attacker model
            attacker = copy.deepcopy(a.args.attacker_model)

            # Setup each attacker model
            attacker.setup(sim, configuration.sink_id, ident=0)

            sim.add_attacker(attacker)

            try:
                sim.run()
            except Exception as ex:
                import traceback
                
                all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                print("Killing run due to {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print(all_args, file=sys.stderr)

                return 51

            proc.stdout.close()

            return_code = proc.wait()

            if return_code:
                raise subprocess.CalledProcessError(return_code, command)

            try:
                sim.metrics.print_results()
            except Exception as ex:
                import traceback

                all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                print("Failed to print metrics due to: {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print(all_args, file=sys.stderr)
                
                return 52

            if print_warnings:
                sim.metrics.print_warnings()

BLOCK0_RE = re.compile(r"=={ Energy consumption results for node (\d+) }=*\nNode lifetime: (\d+) cycles,\s*(.+) seconds")
BLOCKN_NAME_RE = re.compile(r"([A-Za-z]+): (.+) Joule")
JOULE_AND_CYCLES_RE = re.compile(r"(.+) Joule, (\d+) cycles")

JouleAndCycles = namedtuple('JouleAndCycles', ('joule', 'cycles'), verbose=False)

class NodeEnergy:
    def __init__(self, text):

        blocks = text.strip().split("\n\n")

        # Block 0 should be the node id and lifetime stats
        match = BLOCK0_RE.match(blocks[0])
        if match is not None:
            self.nid = int(match.group(1))
            self.node_lifetime_cycles = int(match.group(2))
            self.node_lifetime_seconds = float(match.group(3))
        else:
            raise RuntimeError("Unable to parse '{}' bad BLOCK0_RE".format(blocks[0]))

        self.components = {}

        # Remaining blocks are info about individual components

        for block in blocks[1:]:
            lines = block.split("\n")

            match = BLOCKN_NAME_RE.match(lines[0].strip())
            if match is not None:
                name = match.group(1)
                name_total_joules = float(match.group(2))
            else:
                raise RuntimeError("Unable to parse '{}' bad BLOCKN_NAME_RE".format(lines[0]))

            details = {}

            for line in lines[1:]:
                split_line = line.strip().split(":")

                detail_name, detail_energy = split_line[0], split_line[-1]

                match = JOULE_AND_CYCLES_RE.match(detail_energy)
                if match is not None:
                    jc = JouleAndCycles(float(match.group(1)), float(match.group(2)))
                else:
                    raise RuntimeError("Unable to parse '{}' bad JOULE_AND_CYCLES_RE".format(line))

                details[detail_name] = jc

            self.components[name] = (name_total_joules, details)

    def total_joules(self):
        return sum(joules for (joules, details) in self.components.values())

    def cpu_active_percent(self):
        return self.components["CPU"][1]["Active"].cycles / self.node_lifetime_cycles

    def cpu_idle_percent(self):
        return self.components["CPU"][1]["Idle"].cycles / self.node_lifetime_cycles

    def cpu_low_power_percent(self):
        cpu =  self.components["CPU"][1]
        return (self.node_lifetime_cycles - (cpu["Active"].cycles + cpu["Idle"].cycles)) / self.node_lifetime_cycles

    def radio_active_percent(self):
        radio =  self.components["Radio"][1]
        return (self.node_lifetime_cycles - (radio["Power Off"].cycles + radio["Power Down"].cycles)) / self.node_lifetime_cycles

    def encode(self):
        return base64.b64encode(pickle.dumps(self, pickle.HIGHEST_PROTOCOL))

    @staticmethod
    def decode(input_text):
        return pickle.loads(base64.b64decode(input_text))
