from __future__ import print_function

import math
import sys

from data import latex

class TableDataFormatter(object):
    def __init__(self, convert_to_stddev=False):
        self.convert_to_stddev = convert_to_stddev

    def format_header(self, name):
        try:
            return {
                "network size": ("Network Size", "nodes"),
                "repeats": ("Repeats", "~"),

                "source period": ("$P_{src}$", "(sec)"),
                "fake period": ("$P_{fs}$", "(sec)"),
                "temp fake duration": ("Dur", "(sec)"),
                "pr(tfs)": ("P[TFS]", "(\\%)"),
                "pr(pfs)": ("P[PFS]", "(\\%)"),
                "short walk length": ("Short Walk Length", "(hops)"),
                "long walk length": ("Long Walk Length", "(hops)"),
                "captured": ("Cap", "(\\%)"),
                "reached upper bound": ("RUB", "(\\%)"),
                "fake": ("Fake", "Messages"),
                "dummy normal": ("Dummy Normal", "Messages"),
                "received ratio": ("Received", "(\\%)"),
                "tfs": ("TFS", "~"),
                "pfs": ("PFS", "~"),
                "tailfs": ("TailFS", "~"),
                "pull back hops": ("Pull Back", "Messages"),
                "ssd": ("$\\Delta_{ss}$", "(hops)"),
                "normal latency": ("Laten", "(msec)"),
                "approach": ("Approach", "~"),
                "time taken": ("Time", "(sec)"),
                "safety period": ("Safety Period", "(sec)"),
                "wall time": ("Wall Time", "(sec)"),
                "total wall time": ("Total Wall Time", "(sec)"),
                "first normal sent time": ("FNST", "(sec)"),
                "event count": ("Event Count", ""),
                
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
                "msg group size": ("Msg Group", "Size"),

                "failed avoid sink": ("Failed Avoid", "Sink (\\%)"),
                "failed avoid sink when captured": ("Failed Avoid", "Sink (Cap) (\\%)"),

                "energy impact": ("Energy", ""),
                "energy impact per node": ("Energy", "$\\Sigma^{-1}$"),
                "energy impact per node per second": ("Energy", "$\\Sigma^{-1}$ $s^{-1}$"),

                "norm(sent,time taken)": ("$M$ $T^{-1}$", "~"),
                "norm(norm(sent,time taken),network size)": ("$M$ $T^{-1}$ $\\Sigma^{-1}$", "~"),
                "norm(norm(norm(sent,time taken),network size),source_rate)": ("$M$ $T^{-1}$ $\\Sigma^{-1}$ $R^{-1}$", "~"),
            }[name]
        except KeyError as ex:
            print("Failed to find the name '{}'. Using default. : {}".format(name, ex), file=sys.stderr)
            return (name, "~")

    def _convert_variance(self, variance):
        if self.convert_to_stddev:
            return math.sqrt(variance)
        else:
            return variance

    def format_value(self, name, value):
        if value is None:
            return "None"
        elif name in {"source period", "fake period", "walk length", "walk retries",
                      "repeats", "short walk length", "long walk length"}:
            return "${}$".format(value)
        elif name in {"duration", "temp fake duration"}:
            return "${:.0f}$".format(value)
        elif name == "pr(tfs)" or name == "pr(pfs)":
            return "${:.0f}$".format(value * 100.0)
        elif name in {"tfs", "pfs", "tailfs"}:
            return "${:.1f}$".format(value[0])
        elif name == "approach":
            return latex.escape(value.replace("_APPROACH", ""))
        elif name in {"landmark node"}:
            return latex.escape(value)
        elif name.startswith("energy impact"):
            return "${:.5f}$".format(value[0])
        elif name in {"received ratio", "ssd", "paths reached end"}:
            return "${:.1f} \\pm {:.1f}$".format(value[0], self._convert_variance(value[1]))
        elif name in {"sent", "received", "delivered",
                      "fake", "away", "choose", "dummy normal",
                      "normal latency"}:
            return "${:.0f} \\pm {:.0f}$".format(value[0], self._convert_variance(value[1]))
        elif isinstance(value, dict):
            return latex.escape(str(value))
        elif isinstance(value, float):
            return "${:.2f}$".format(value)
        elif isinstance(value, int):
            return "${}$".format(value)
        else:
            try:
                if isinstance(value[0], dict):
                    return "${} \\pm {}$".format(value[0], self._convert_variance(value[1]))
                else:
                    return "${:.3f} \\pm {:.3f}$".format(value[0], self._convert_variance(value[1]))
            except TypeError as e:
                raise RuntimeError("Unable to format values for {} with values {} under the default settings. (HINT: You might need to add a custom formatter in this function)".format(name, value), e)
