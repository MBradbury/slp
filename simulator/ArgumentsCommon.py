
import argparse
from random import SystemRandom

import simulator.Attacker as Attacker
import simulator.common
import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel
import simulator.FaultModel as FaultModel
import simulator.sim

from data import submodule_loader

def _secure_random():
    """Returns a random 32 bit (4 byte) signed integer"""
    # From: https://stackoverflow.com/questions/9216344/read-32-bit-signed-value-from-an-unsigned-bytestream
    rno = SystemRandom().getrandbits(32)

    if rno >> 31: # is the sign bit set?
        return -0x80000000 + (rno & 0x7fffffff) # "cast" it to signed

    return rno

def _add_safety_period(parser, has_safety_period=False, has_safety_factor=False, **kwargs):
    if has_safety_period:
        parser.add_argument("-safety", "--safety-period",
                            type=ArgumentsCommon.type_positive_float,
                            required=True)

        if has_safety_factor:
            parser.add_argument("--safety-factor",
                                type=ArgumentsCommon.type_positive_float,
                                required=False,
                                default=1.0)

def _add_low_powered_listening(parser, **kwargs):
    parser.add_argument("-lpl", "--low-power-listening", choices=("enabled", "disabled"), required=False, default="disabled")
    parser.add_argument("--lpl-local-wakeup", type=ArgumentsCommon.type_positive_int, required=False, default=None,
                        help="This is the period for which a node will turn the radio off.")

    parser.add_argument("--lpl-remote-wakeup", type=ArgumentsCommon.type_positive_int, required=False, default=None,
                        help="This is a global setting, that configures a messages to be transmitted within a given wakeup period.")

    parser.add_argument("--lpl-delay-after-receive", type=ArgumentsCommon.type_positive_int, required=False, default=None,
                        help="How long should the radio be kept on after a message is received.")

    parser.add_argument("--lpl-max-cca-checks", type=ArgumentsCommon.type_positive_int, required=False, default=None,
                        help="The maximum number of CCA checks performed on each wakeup.")

def _add_avrora_radio_model(parser, **kwargs):
    import simulator.AvroraRadioModel as AvroraRadioModel

    parser.add_argument("-rm", "--radio-model", type=AvroraRadioModel.eval_input, required=True)

def _add_log_converter(parser, **kwargs):
    import simulator.OfflineLogConverter as OfflineLogConverter

    parser.add_argument("--log-converter", type=str, choices=OfflineLogConverter.names(), required=True)

OPTS = {
    "configuration":       lambda x, **kwargs: x.add_argument("-c", "--configuration",
                                                              type=str,
                                                              required=True,
                                                              choices=Configuration.names()),

    "verbose":             lambda x, **kwargs: x.add_argument("-v", "--verbose",
                                                              action="store_true"),

    "seed":                lambda x, **kwargs: x.add_argument("--seed",
                                                              type=int,
                                                              required=False),

    "network size":        lambda x, **kwargs: x.add_argument("-ns", "--network-size",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              required=True),

    "distance":            lambda x, **kwargs: x.add_argument("-d", "--distance",
                                                              type=ArgumentsCommon.type_positive_float,
                                                              default=4.5),

    "node id order":       lambda x, **kwargs: x.add_argument("-nido", "--node-id-order",
                                                              choices=("topology", "randomised"),
                                                              default="topology"),

    "safety period":       _add_safety_period,
        

    "communication model": lambda x, **kwargs: x.add_argument("-cm", "--communication-model",
                                                              type=str,
                                                              choices=simulator.common.available_communication_models(),
                                                              required=True),

    "noise model":         lambda x, **kwargs: x.add_argument("-nm", "--noise-model",
                                                              type=str,
                                                              choices=simulator.common.available_noise_models(),
                                                              required=True),

    # Only for Avrora
    "radio model":         _add_avrora_radio_model,

    "attacker model":      lambda x, **kwargs: x.add_argument("-am", "--attacker-model",
                                                              type=Attacker.eval_input,
                                                              required=True),

    "fault model":         lambda x, **kwargs: x.add_argument("-fm", "--fault-model",
                                                              type=FaultModel.eval_input,
                                                              required=False,
                                                              default=FaultModel.ReliableFaultModel()),

    "start time":          lambda x, **kwargs: x.add_argument("-st", "--latest-node-start-time",
                                                              type=ArgumentsCommon.type_positive_float,
                                                              required=False,
                                                              default=1.0,
                                                              help="Used to specify the latest possible start time in seconds. Start times will be chosen in the inclusive random range [0, x] where x is the value specified."),

    # See http://www.ti.com/lit/ds/symlink/cc2420.pdf section 28
    # This is for chips with a CC2420 only
    # TOSSIM DOES NOT SIMULATE THIS!
    "rf power":            lambda x, **kwargs: x.add_argument("--rf-power",
                                                              type=int,
                                                              choices=[3, 7, 11, 15, 19, 23, 27, 31],
                                                              required=False,
                                                              default=None,
                                                              help="Used to set the power levels for the CC2420 radio chip. 3 is low, 31 is high."),

    "gui node label":      lambda x, **kwargs: x.add_argument("--gui-node-label",
                                                              type=str,
                                                              required=False,
                                                              default=None),

    "gui scale":           lambda x, **kwargs: x.add_argument("--gui-scale",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              required=False,
                                                              default=6),

    "job size":            lambda x, **kwargs: x.add_argument("--job-size",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              required=True),

    "thread count":        lambda x, **kwargs: x.add_argument("--thread-count",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              default=None),

    "job id":              lambda x, **kwargs: x.add_argument("--job-id",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              default=None,
                                                              help="Used to pass the array id when this job has been submitted as a job array to the cluster."),

    "log file":            lambda x, **kwargs: x.add_argument("--log-file",
                                                              type=str,
                                                              nargs="+",
                                                              metavar="F",
                                                              required=True),

    "log converter":        _add_log_converter,

    "low powered listening": _add_low_powered_listening,

    "max buffer size":     lambda x, **kwargs: x.add_argument("--max-buffer-size",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              default=255),
}

class ArgumentsCommon(object):
    def __init__(self, description, has_safety_period=False, has_safety_factor=False):
        self._parser = argparse.ArgumentParser(description=description, add_help=True)

        self._subparsers = {}

        simparsers = self._parser.add_subparsers(title="sim", dest="sim",
                                                 help="The tool you wish to use to run your algorithm.")

        for sim in submodule_loader.list_available(simulator.sim):

            self._subparsers[sim] = {}

            parser_sim = simparsers.add_parser(sim, add_help=True)

            subparsers = parser_sim.add_subparsers(title="mode", dest="mode",
                                                   help="The mode you wish to run the simulation in.")

            sim_mode = submodule_loader.load(simulator.sim, sim)
            for (mode, inherit, opts) in sim_mode.parsers():

                parents = (self._subparsers[sim][inherit],) if inherit is not None else tuple()

                parser_sub = subparsers.add_parser(mode, add_help=False, parents=parents)

                self._subparsers[sim][mode] = parser_sub

                for opt in opts:
                    OPTS[opt](parser_sub,
                              has_safety_period=has_safety_period,
                              has_safety_factor=has_safety_factor)

        # Haven't parsed anything yet
        self.args = None

        # Don't show these arguments when printing the argument values before showing the results
        self.arguments_to_hide = {"job_id", "verbose", "gui_node_label", "gui_scale", "mode", "seed", "thread_count"}

    def add_argument(self, *args, **kwargs):
        for sim in self._subparsers:
            if sim == "offline":
                continue

            for parser in self._subparsers[sim].values():
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

        #if hasattr(self.args, 'seed'):
        #  result["SLP_SEED"] = "UINT32_C({})".format(self.args.seed)

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

        if hasattr(self.args, 'fault_model'):
          result.update(self.args.fault_model.build_arguments())

        if hasattr(self.args, 'low_power_listening'):

            if self.args.low_power_listening == "enabled":
                result["LOW_POWER_LISTENING"] = 1

                # See SystemLowPowerListeningP.nc for how this macro is used
                if self.args.lpl_remote_wakeup is not None:
                    result["LPL_DEF_REMOTE_WAKEUP"] = self.args.lpl_remote_wakeup

                # See PowerCycleP.nc for how this macro is used
                if self.args.lpl_local_wakeup is not None:
                    result["LPL_DEF_LOCAL_WAKEUP"] = self.args.lpl_local_wakeup

                # See SystemLowPowerListeningP.nc for how this macro is used
                if self.args.lpl_delay_after_receive is not None:
                    result["DELAY_AFTER_RECEIVE"] = self.args.lpl_delay_after_receive

                # See DefaultLpl.h for definition
                #
                # Other values than the default might be good.
                # The following link recommends 1600
                # See http://mail.millennium.berkeley.edu/pipermail/tinyos-help/2011-June/051478.html
                if self.args.lpl_max_cca_checks is not None:
                    result["MAX_LPL_CCA_CHECKS"] = self.args.lpl_max_cca_checks

        if hasattr(self.args, 'rf_power'):
            if self.args.rf_power is not None:
                # TODO: consider setting the values for alternate drivers (CC2420X, ...)
                result['CC2420_DEF_RFPOWER'] = self.args.rf_power

        return result

    def _get_node_id(self, topo_node_id_str):
        """Gets the topology node id from a node id string.
        This value could either be the topology node id as an integer,
        or it could be an attribute of the topology or configuration (e.g., 'sink_id')."""
        configuration = Configuration.create(self.args.configuration, self.args)

        return configuration.get_node_id(topo_node_id_str)

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
