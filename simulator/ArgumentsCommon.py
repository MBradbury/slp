
import argparse
from random import SystemRandom

import simulator.Attacker as Attacker
import simulator.common
import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel

from data import submodule_loader
import data.cycle_accurate

# Inheritance diagram for different modes:
# TESTBED < CYCLEACCURATE
#         < SINGLE  < PARALLEL    < CLUSTER
#                   < GUI
#         < OFFLINE < OFFLINE_GUI

def _secure_random():
    """Returns a random 32 bit (4 byte) signed integer"""
    # From: https://stackoverflow.com/questions/9216344/read-32-bit-signed-value-from-an-unsigned-bytestream
    rno = SystemRandom().getrandbits(32)

    if rno >> 31: # is the sign bit set?
        return -0x80000000 + (rno & 0x7fffffff) # "cast" it to signed

    return rno

class ArgumentsCommon(object):
    def __init__(self, description, has_safety_period=False, has_safety_factor=False):
        parser = argparse.ArgumentParser(description=description, add_help=False)

        subparsers = parser.add_subparsers(title="mode", dest="mode")

        ###

        parser_testbed = subparsers.add_parser("TESTBED", add_help=True)

        parser_testbed.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())

        parser_testbed.add_argument("-v", "--verbose", action="store_true")

        ###

        parser_cycle = subparsers.add_parser("CYCLEACCURATE", add_help=False, parents=(parser_testbed,))

        parser_cycle.add_argument("--seed", type=int, required=False)

        parser_cycle.add_argument("-ns", "--network-size", type=self.type_positive_int, required=True)
        parser_cycle.add_argument("-d", "--distance", type=self.type_positive_float, default=4.5)

        parser_cycle.add_argument("--node-id-order", choices=("topology", "randomised"), default="topology")

        if has_safety_period:
            parser_cycle.add_argument("-safety", "--safety-period", type=self.type_positive_float, required=True)

            if has_safety_factor:
                parser_cycle.add_argument("--safety-factor", type=self.type_positive_float, required=False, default=1.0)

        ###

        parser_single = subparsers.add_parser("SINGLE", add_help=False, parents=(parser_cycle,))

        parser_single.add_argument("-cm", "--communication-model", type=str, choices=simulator.common.available_communication_models(), required=True)
        parser_single.add_argument("-nm", "--noise-model", type=str, choices=simulator.common.available_noise_models(), required=True)

        parser_single.add_argument("-am", "--attacker-model", type=Attacker.eval_input, required=True)

        parser_single.add_argument("-st", "--latest-node-start-time", type=self.type_positive_float, required=False, default=1.0,
                                   help="Used to specify the latest possible start time in seconds. Start times will be chosen in the inclusive random range [0, x] where x is the value specified.")

        ###

        # The profile parser is the same as the single parser
        # The only difference is that the code will not be rebuilt.
        parser_profile = subparsers.add_parser("PROFILE", add_help=False, parents=(parser_single,))

        ###

        parser_gui = subparsers.add_parser("GUI", add_help=False, parents=(parser_single,))

        parser_gui.add_argument("--gui-node-label", type=str, required=False, default=None)
        parser_gui.add_argument("--gui-scale", type=self.type_positive_int, required=False, default=6)

        ###

        parser_parallel = subparsers.add_parser("PARALLEL", add_help=False, parents=(parser_single,))

        parser_parallel.add_argument("--job-size", type=self.type_positive_int, required=True)
        parser_parallel.add_argument("--thread-count", type=self.type_positive_int, default=None)

        ###

        parser_cluster = subparsers.add_parser("CLUSTER", add_help=False, parents=(parser_parallel,))

        parser_cluster.add_argument("--job-id", type=self.type_positive_int, default=None,
                                    help="Used to pass the array id when this job has been submitted as a job array to the cluster.")

        ###
        ###

        parser_offline = subparsers.add_parser("OFFLINE", add_help=False, parents=(parser_cycle,))

        parser_offline.add_argument("--merged-log", type=str, required=True)

        parser_offline.add_argument("-am", "--attacker-model", type=Attacker.eval_input, required=True)

        ###

        parser_offline_gui = subparsers.add_parser("OFFLINE_GUI", add_help=False, parents=(parser_offline,))

        parser_offline_gui.add_argument("--gui-scale", type=self.type_positive_int, required=False, default=6)

        ###
        ###

        # Add extra parameters that we did not want being inherited

        # Testbed and cycle accurate simulators can work with LowPowerListening, but TOSSIM doesn't
        for sub_parser in (parser_testbed, parser_cycle):
            sub_parser.add_argument("-lpl", "--low-power-listening", choices=("enabled", "disabled"), required=False, default="disabled")
            sub_parser.add_argument("--lpl-local-wakeup", type=self.type_positive_int, required=False, default=-1)
            sub_parser.add_argument("--lpl-remote-wakeup", type=self.type_positive_int, required=False, default=-1)
            sub_parser.add_argument("--lpl-delay-after-receive", type=self.type_positive_int, required=False, default=-1)

        parser_cycle.add_argument("simulator", type=str, choices=submodule_loader.list_available(data.cycle_accurate))

        ###
        ###

        # Store any of the parsers that we need
        self._parser = parser
        self._online_subparsers = (parser_testbed, parser_cycle, parser_single, parser_profile, parser_gui, parser_parallel, parser_cluster)
        self._offline_subparsers = (parser_offline, parser_offline_gui)

        # Haven't parsed anything yet
        self.args = None

        # Don't show these arguments when printing the argument values before showing the results
        self.arguments_to_hide = {"job_id", "verbose", "gui_node_label", "gui_scale", "mode", "seed", "thread_count"}

    def add_argument(self, *args, **kwargs):

        # TODO: Work out a way to just add this to a single subparser and let the argument
        # trickle down to the other subparsers.

        for parser in self._online_subparsers:
            parser.add_argument(*args, **kwargs)

    def parse(self, argv):
        self.args = self._parser.parse_args(argv)

        if hasattr(self.args, 'seed'):
            if self.args.seed is None:
                self.args.seed = _secure_random()

        if hasattr(self.args, 'source_mobility'):
            configuration = Configuration.create(self.args.configuration, self.args)
            self.args.source_mobility.setup(configuration)
        
        return self.args

    def build_arguments(self):
        result = {}

        if self.args.verbose:
            result["SLP_VERBOSE_DEBUG"] = 1

        # Only enable things like LEDS for the cases that we will use them
        # We could enable them for the testbed, but we get better reliability and performance by not doing so
        if self.args.mode == "GUI":
            result["SLP_USES_GUI_OUPUT"] = 1

        # Source period could either be a float or a class derived from PeriodModel
        if hasattr(self.args, 'source_period'):
            if isinstance(self.args.source_period, float):
                if float(self.args.source_period) <= 0:
                    raise RuntimeError("The source_period ({}) needs to be greater than 0".format(self.args.source_period))

                result["SOURCE_PERIOD_MS"] = int(self.args.source_period * 1000)
            elif isinstance(self.args.source_period, SourcePeriodModel.PeriodModel):
                result.update(self.args.source_period.build_arguments())
            else:
                raise RuntimeError("The source_period ({}) either needs to be a float or an instance of SourcePeriodModel.PeriodModel".format(self.args.source_period))

        if hasattr(self.args, 'source_mobility'):
            result.update(self.args.source_mobility.build_arguments())
        else:
            # If there are no mobility models provided, then the only source specified
            # by the configuration can be used instead.
            # This is mainly for legacy algorithm support, StationaryMobilityModels
            # are a better choice for new algorithms.

            configuration = Configuration.create(self.args.configuration, self.args)

            if len(configuration.source_ids) != 1:
                raise RuntimeError("Invalid number of source ids in configuration {}, there must be exactly one.".format(configuration))

            (source_id,) = configuration.source_ids

            result["SOURCE_NODE_ID"] = configuration.topology.to_topo_nid(source_id)

        if hasattr(self.args, 'low_power_listening'):
            # Negative indicates disabled

            if self.args.low_power_listening == "enabled":
                result["LOW_POWER_LISTENING"] = 1

                # See SystemLowPowerListeningP.nc for how this macro is used
                if self.args.lpl_remote_wakeup >= 0:
                    result["LPL_DEF_REMOTE_WAKEUP"] = self.args.lpl_remote_wakeup

                # See PowerCycleP.nc for how this macro is used
                if self.args.lpl_local_wakeup >= 0:
                    result["LPL_DEF_LOCAL_WAKEUP"] = self.args.lpl_local_wakeup

                # See SystemLowPowerListeningP.nc for how this macro is used
                if self.args.lpl_delay_after_receive >= 0:
                    results["DELAY_AFTER_RECEIVE"] = self.args.lpl_delay_after_receive

        return result

    def _get_node_id(self, topo_node_id_str):
        """Gets the topology node id from a node id string.
        This value could either be the topology node id as an integer,
        or it could be an attribute of the topology or configuration (e.g., 'sink_id')."""
        configuration = Configuration.create(self.args.configuration, self.args)

        try:
            topo_node_id = int(topo_node_id_str)

            ord_node_id = configuration.topology.to_ordered_nid(topo_node_id)

            if ord_node_id not in configuration.topology.nodes:
                raise RuntimeError("The node id {} is not a valid node id".format(topo_node_id))

            return topo_node_id

        except ValueError:
            attr_sources = (configuration, configuration.topology)
            for attr_source in attr_sources:
                if hasattr(attr_source, topo_node_id_str):
                    ord_node_id = int(getattr(attr_source, topo_node_id_str))

                    return configuration.topology.to_topo_nid(ord_node_id)

            raise RuntimeError("No way to work out node from {}.".format(topo_node_id_str))

    @staticmethod
    def type_probability(x):
        x = float(x)
        if x < 0.0 or x > 1.0:
            raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
        return x

    @staticmethod
    def type_positive_int(x):
        x = int(x)
        if x < 0:
            raise argparse.ArgumentTypeError("{} must be positive".format(x))
        return x

    @staticmethod
    def type_positive_float(x):
        x = float(x)
        if x < 0:
            raise argparse.ArgumentTypeError("{} must be positive".format(x))
        return x
