from __future__ import print_function

import math
import sys

from data import latex

class TableDataFormatter(object):
    def __init__(self):
        super().__init__()

    def format_header(self, name):
        try:
            return {
                "network size": ("Network Size", "nodes"),
                "repeats": ("Repeats", "~"),
                "safety factor": ("Safety", "Factor"),

                "source period": ("$P_{src}$", "(sec)"),
                "fake period": ("$P_{fs}$", "(sec)"),
                "temp fake duration": ("Dur", "(sec)"),
                "pr(tfs)": ("P[TFS]", "(\\%)"),
                "pr(pfs)": ("P[PFS]", "(\\%)"),
                "short walk length": ("Short Walk Length", "(hops)"),
                "long walk length": ("Long Walk Length", "(hops)"),
                "captured": ("Captured", "(\\%)"),
                "reached upper bound": ("RUB", "(\\%)"),
                "fake": ("Fake", "Messages"),
                "dummy normal": ("Dummy Normal", "Messages"),
                "received ratio": ("Received", "(\\%)"),
                "tfs": ("TFS", "~"),
                "pfs": ("PFS", "~"),
                "tailfs": ("TailFS", "~"),
                "pull back hops": ("Pull Back", "Messages"),
                "ssd": ("$\\Delta_{ss}$", "(hops)"),
                "normal latency": ("Latency", "(msec)"),
                "approach": ("Approach", "~"),
                "time taken": ("Time Taken", "(sec)"),
                "safety period": ("Safety Period", "(sec)"),
                "wall time": ("Wall Time", "(sec)"),
                "total wall time": ("Total Wall", "Time (sec)"),
                "first normal sent time": ("FNST", "(sec)"),
                "event count": ("Event Count", ""),
                "memory rss": ("Memory", "RSS (MB)"),
                "memory vms": ("Memory", "VMS (MB)"),

                "pr tfs": ("Pr(TFS)", "(\\%)"),
                "pr pfs": ("Pr(PFS)", "(\\%)"),
                
                "walk length": ("Walk Length", "(hops)"),
                "walk retries": ("Walk", "Retries"),
                "paths reached end": ("Paths Ended", "(\\%)"),

                "slot period": ("Slot", "Period"),
                "dissem period": ("Dissem", "Period"),
                "dissem timeout": ("Dissem", "Timeout"),
                "tdma num slots": ("Num", "Slots"),
                "slot assignment interval": ("Ass.", "Int."),
                "minimum setup periods": ("Min Setup", "Periods"),
                "pre beacon periods": ("Pre Beacon", "Periods"),
                "search distance": ("Search", "Distance"),

                "buffer size": ("Buffer", "Size"),
                "max walk length": ("Max Walk", "Length (hops)"),
                "pr direct to sink": ("Pr Direct", "to Sink"),
                "msg group size": ("Grp", "Size"),

                "failed avoid sink": ("Failed Avoid", "Sink (\\%)"),
                "failed avoid sink when captured": ("Failed Avoid", "Sink (Cap) (\\%)"),

                "energy impact": ("Energy", ""),
                "energy impact per node": ("Energy", "$\\Sigma^{-1}$"),
                "energy impact per node per second": ("Energy", "$\\Sigma^{-1}$ $s^{-1}$"),

                "norm(sent,time taken)": ("Messages Sent", "Per Second"),
                "norm(norm(sent,time taken),network size)": ("Messages Sent Per Node", "Per Second"),
                "norm(norm(norm(sent,time taken),network size),source_rate)": ("$M$ $T^{-1}$ $\\Sigma^{-1}$ $R^{-1}$", "~"),

                "norm(norm(fake,time taken),network size)": ("$\\mathcal{F}$ $T^{-1}$ $\\Sigma^{-1}$", "~"),

                "protected sink hops": ("Protected", "Sink Hops"),
                "activate period": ("$P_{activate}$", "(sec)"),
                "cone type": ("Cone", "Type"),

                "lpl normal early": ("$W_{e}(\\mathcal{N})$", "ms"),
                "lpl normal late": ("$W_{l}(\\mathcal{N})$", "ms"),
                "lpl fake early": ("$W_{e}(\\mathcal{F})$", "ms"),
                "lpl fake late": ("$W_{l}(\\mathcal{F})$", "ms"),
                "lpl choose early": ("$W_{e}(\\mathcal{C})$", "ms"),
                "lpl choose late": ("$W_{l}(\\mathcal{C})$", "ms"),

                "lpl remote wakeup": ("RW", "ms"),
                "lpl local wakeup": ("LW", "ms"),
                "lpl delay after receive": ("DAR", "ms"),
                "lpl max cca checks": ("CCA", "~"),

                "average duty cycle": ("Duty Cycle", "(\\%)"),

                "attacker distance": ("Attacker", "Distance"),
            }[name]
        except KeyError as ex:
            print("Failed to find the name '{}'. Using default. : {}".format(name, ex), file=sys.stderr)
            return (name, "~")

    def format_value(self, name, value):

        pmvalue = "ci95" #"std"

        if value is None:
            return "None"
        elif name in {"source period", "fake period", "walk length", "walk retries",
                      "repeats", "short walk length", "long walk length"}:
            return str(value)
        elif name in {"duration", "temp fake duration",
                      "lpl normal early", "lpl normal late",
                      "lpl fake early", "lpl fake late",
                      "lpl choose early", "lpl choose late"}:
            return "${:.0f}$".format(value)
        elif name in {"pr tfs", "pr pfs", "pr direct to sink"}:
            return "${:.0f}$".format(value * 100.0)
        elif name == "average duty cycle":
            return "${:.2f}$".format(value['mean'])
        elif name in {"tfs", "pfs", "tailfs"}:
            return "${:.1f}$".format(value[0])
        elif name == "approach":
            return latex.escape(value.replace("_APPROACH", "").replace("PB_", ""))
        elif name in {"landmark node", "cone type"}:
            return latex.escape(value)
        #elif name.startswith("energy impact"):
        #    return "${:.5f}$".format(value[0])
        elif name in {"received ratio", "ssd", "paths reached end"}:
            return "${:.1f} \\pm {:.1f}$".format(value['mean'], value[pmvalue])
        elif name in {"sent", "received", "delivered",
                      "fake", "away", "choose", "dummy normal",
                      "normal latency", "event count",
                      "norm(sent,time taken)"}:
            return "${:.0f} \\pm {:.2f}$".format(value['mean'], value[pmvalue])
        elif name in {"memory rss", "memory vms"}:
            factor = 1024 * 1024 # Bytes to MB
            return "${:.0f} \\pm {:.0f}$".format(value['mean'] / factor, value[pmvalue] / factor)
        elif isinstance(value, dict):
            if 'mean' in value:
                return "${:.3f} \\pm {:.3f}$".format(value['mean'], value[pmvalue])
            else:
                return latex.escape(str(value))
        elif isinstance(value, float):
            return "${:.2f}$".format(value)
        elif isinstance(value, int):
            return "${}$".format(value)
        elif isinstance(value, str):
            return value
        else:
            try:
                if isinstance(value[0], dict):
                    return "${} \\pm {}$".format(value['mean'], value[pmvalue])
                elif isinstance(value, dict):
                    return "${:.3f} \\pm {:.3f}$".format(value['mean'], value[pmvalue])
                else:
                    raise RuntimeError("Unable to format values for {} with values {} under the default settings. (HINT: You might need to add a custom formatter in this function)".format(name, value))
            except TypeError as e:
                raise RuntimeError("Unable to format values for {} with values {} under the default settings. (HINT: You might need to add a custom formatter in this function)".format(name, value), e)


class ShortTableDataFormatter(TableDataFormatter):
    def __init__(self):
        super().__init__()

    def format_header(self, name):
        try:
            return {
                "approach": ("App.", "~"),

                "repeats": ("R", "~"),
                "time taken": ("$\\mathcal{TT}$", "(sec)"),
                "received ratio": ("Received", "(\\%)"),
                "captured": ("Captured", "(\\%)"),
                "normal latency": ("Latency", "(ms)"),
                "attacker distance": ("Attacker", "Distance"),
                "sent": ("Sent", "~"),
                "norm(sent,time taken)": ("Sent", "per sec"),
                "pr tfs": ("PrTFS", "(\\%)"),
                "pr direct to sink": ("PDS", "(\\%)"),
            }[name]
        except KeyError as ex:
            return super().format_header(name)

    lpl_conv = {
        (200, 200, 250, 250 ,75, 75): 1,
        (80, 80, 120, 130, 5, 50): 2,
        (40, 40, 120, 130, 5, 50): 3,
        (35, 35, 100, 100, 5, 50): 4,
        (35, 35, 60, 60, 5, 50): 5,

        (200, 200, 120, 130, 75, 75): 6, # Only for FlockLab
    }

    tinyoslpl_conv = {
        (50, 50, 10, 1150): 1,
        (50, 50, 100, 400): 2,
        (75, 75, 10, 1150): 3,
        (75, 75, 10, 2300): 4,
        (75, 75, 100, 400): 5,
    }

    def format_value(self, name, value):
        if name == ('lpl normal early', 'lpl normal late', 'lpl fake early', 'lpl fake late', 'lpl choose early', 'lpl choose late'):
            return str(self.lpl_conv.get(value, value))
        elif name == ('lpl local wakeup', 'lpl remote wakeup', 'lpl delay after receive', 'lpl max cca checks'):
            return str(self.tinyoslpl_conv.get(value, value))
        elif name == "approach":

            return {
                "PB_FIXED1_APPROACH": "Fxd1",
                "PB_FIXED2_APPROACH": "Fxd2",
                "PB_ATTACKER_EST_APPROACH": "AEst",

            }.get(value, latex.escape(value.replace("_APPROACH", "").replace("PB_", "")))
        else:
            return super().format_value(name, value)
