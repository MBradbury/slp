from __future__ import print_function, division

import ast
from collections import OrderedDict, Sequence
import datetime
import fnmatch
import math
import multiprocessing
from numbers import Number
import os
import re
import sys
import timeit
import traceback

from  more_itertools import unique_everseen
import numpy as np
import pandas as pd

from data.memoize import memoize
import simulator.common
import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel

class EmptyFileError(RuntimeError):
    def __init__(self, filename):
        super(EmptyFileError, self).__init__("The file '{}' is empty.".format(filename))


def _normalised_value_name(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, Sequence) and len(value) == 2:
        return "norm({},{})".format(_normalised_value_name(value[0]), _normalised_value_name(value[1]))
    else:
        raise RuntimeError("Unknown type or length for value '{}' of type {}".format(value, type(value)))

def _dfs_names(value):
    result = []

    if isinstance(value, str):
        #result.append(value)
        pass
    elif isinstance(value, Sequence) and len(value) == 2:
        result.extend(_dfs_names(value[0]))
        result.extend(_dfs_names(value[1]))
        result.append(_normalised_value_name(value))
    else:
        raise RuntimeError("Unknown type or length for value '{}' of type {}".format(value, type(value)))

    return result

def _normalised_value_names(values):
    all_results = []

    for value in values:
        all_results.extend(_dfs_names(value))

    unique_results = tuple(unique_everseen(all_results))

    return unique_results

def _inf_handling_literal_eval(item):
     # ast.literal_eval will not parse inf correctly.
    # passing 2e308 will return a float('inf') instead.
    #
    # The fast_eval version will parse inf when on its own correctly,
    # so this hack is not needed there.
    item = item.replace('inf', '2e308')

    return ast.literal_eval(item)

DICT_NODE_KEY_RE = re.compile(r'(\d+):\s*(\d+\.\d+|\d+)\s*(?:,|}$)')

def _parse_dict_node_to_value(indict):
    # Parse a dict like "{1: 10, 2: 20, 3: 40}"

    result = {
        int(a): float(b)
        for (a, b) in DICT_NODE_KEY_RE.findall(indict)
    }

    return result

DICT_TUPLE_KEY_RE = re.compile(r'\((\d+),\s*(\d+)\):\s*(\d+\.\d+|\d+)\s*(?:,|}$)')
DICT_TUPLE_KEY_OLD_RE = re.compile(r'(\d+):\s*(\d+\.\d+|\d+)\s*(?:,|}$)')

def _parse_dict_tuple_nodes_to_value(indict):
    # Parse a dict like "{(0, 1): 5, (0, 3): 20, (1, 1): 40}"
    # but also handle the old style of "{0: 1}"

    # Handle two sorts of attacker distance dicts
    # 1. {attacker_id: distance}
    # 2. {(source_id, attacker_id): distance}}
    
    # New style
    d1 = {
        (int(a), int(b)): float(c)
        for (a, b, c) in DICT_TUPLE_KEY_RE.findall(indict)
    }

    # Old style - assume the source is 0
    d2 = {
        (0, int(b)): float(c)
        for (b, c) in DICT_TUPLE_KEY_OLD_RE.findall(indict)
    }

    d1.update(d2)

    return d1

class Analyse(object):

    HEADING_DTYPES = {
        "Seed": np.int64,
        "Sent": np.uint32,
        "Captured": np.bool_,
        "Received": np.uint32,
        "ReceiveRatio": np.float_,
        "TimeTaken": np.float_,
        "WallTime": np.float_,
        "EventCount": np.uint64,
        "NormalLatency": np.float_,
        "NormalSinkSourceHops": np.float_,
        "NormalSent": np.uint32,
    }

    HEADING_CONVERTERS = {
        #"Collisions": ast.literal_eval,
        "SentHeatMap": _parse_dict_node_to_value,
        "ReceivedHeatMap": _parse_dict_node_to_value,
        "AttackerDistance": _parse_dict_tuple_nodes_to_value,
        "AttackerMoves": _parse_dict_node_to_value,
        "AttackerStepsAway": _parse_dict_tuple_nodes_to_value,
        "AttackerStepsTowards": _parse_dict_tuple_nodes_to_value,
        "AttackerSinkDistance": _parse_dict_tuple_nodes_to_value,
        "AttackerMinSourceDistance": _parse_dict_tuple_nodes_to_value,
        "NodeWasSource": _inf_handling_literal_eval,
    }

    def __init__(self, infile, normalised_values):

        self.opts = {}

        self.unnormalised_headings = []
        self.columns = {}

        with open(infile, 'r') as f:
            line_number = 0

            for line in f:

                line_number += 1

                # We need to remove the new line at the end of the line
                line = line.strip()

                if len(self.unnormalised_headings) == 0 and '=' in line:
                    # We are reading the options so record them.
                    # Some option values will have an '=' in them so only split once.
                    opt = line.split('=', 1)

                    self.opts[opt[0]] = opt[1]

                elif line.startswith('#'):
                    # Read the headings
                    self.unnormalised_headings = line[1:].split('|')

                    break

        if line_number == 0:
            raise EmptyFileError(infile)

        self._unnormalised_headings_count = len(self.unnormalised_headings)

        self.additional_normalised_headings = _normalised_value_names(normalised_values)

        self.headings = list(self.unnormalised_headings)
        self.headings.extend(self.additional_normalised_headings)

        self.columns = pd.read_csv(infile,
            names=self.unnormalised_headings, header=None,
            sep='|',
            skiprows=line_number,
            dtype=self.HEADING_DTYPES, converters=self.HEADING_CONVERTERS,
            compression=None,
            #verbose=True
        )

        # Removes rows with infs in certain columns
        self.columns = self.columns.replace([np.inf, -np.inf], np.nan)
        self.columns.dropna(subset=["NormalLatency"], how="all")

        for (norm_head, (num, den)) in zip(self.additional_normalised_headings, normalised_values):

            num = _normalised_value_name(num)
            den = _normalised_value_name(den)

            self.columns[norm_head] = self.columns.apply(lambda row: self._get_norm_value(num, den, row),
                axis=1, raw=True, reduce=True)

    @memoize
    def headings_index(self, name):
        return self.headings.index(name)

    def _get_norm_value(self, num, den, row):
        num_value = self._get_from_opts_or_values(num, row)
        den_value = self._get_from_opts_or_values(den, row)

        return np.float_(num_value / den_value)


    def _get_configuration(self):
        return Configuration.create_specific(self.opts['configuration'],
                                             int(self.opts['network_size']),
                                             float(self.opts['distance']))

    def _get_from_opts_or_values(self, name, values):
        try:
            index = self.headings.index(name)

            #print(name + " " + key + " " + str(values))

            return values[index]
        except ValueError:
            if name == "network_size":
                configuration = self._get_configuration()
                return configuration.size()

            elif name == "num_sources":
                configuration = self._get_configuration()
                return len(configuration.source_ids)

            elif name == "source_period":
                # Warning: This will only work for the FixedPeriodModel
                # All other models have variable source periods, so we cannot calculate this
                return float(SourcePeriodModel.eval_input(self.opts["source_period"]))

            elif name == "source_rate":
                source_period = self._get_from_opts_or_values("source_period", values)
                return 1.0 / source_period

            elif name == "source_period_per_num_sources":
                source_period = self._get_from_opts_or_values("source_period", values)
                num_sources = self._get_from_opts_or_values("num_sources", values)
                return source_period / num_sources

            elif name == "source_rate_per_num_sources":
                source_rate = self._get_from_opts_or_values("source_rate", values)
                num_sources = self._get_from_opts_or_values("num_sources", values)
                return source_rate / num_sources

            elif name == "energy_impact":
                # From Great Duck Island paper, in nanoamp hours
                cost_per_bcast_nah = 20.0
                cost_per_deliver_nah = 8.0

                sent = self._get_from_opts_or_values("Sent", values)
                received = self._get_from_opts_or_values("Received", values)

                num_sources = self._get_from_opts_or_values("num_sources", values)

                # The energy cost in milliamp hours
                cost_mah = (sent * cost_per_bcast_nah + received * cost_per_deliver_nah) / 1000000.0

                return cost_mah

            elif name == "daily_allowance_used":
                energy_impact = self._get_from_opts_or_values("energy_impact", values)
                network_size = self._get_from_opts_or_values("network_size", values)
                time_taken = self._get_from_opts_or_values("TimeTaken", values)

                energy_impact_per_node_per_second = (energy_impact / network_size) / time_taken

                energy_impact_per_node_per_day = energy_impact_per_node_per_second * 60.0 * 60.0 * 24.0

                daily_allowance_mah = 6.9

                cpu_power_consumption_ma = 5

                duty_cycle = 0.042

                daily_allowance_mah -= cpu_power_consumption_ma * 24 * duty_cycle

                energy_impact_per_node_per_day_when_active = energy_impact_per_node_per_day * duty_cycle

                return (energy_impact_per_node_per_day_when_active / daily_allowance_mah) * 100.0

            else:
                # Handle normalising with arbitrary numbers
                try:
                    return float(name)
                except ValueError:
                    return float(self.opts[name])

    def check_consistent(self, values, line_number):
        """Perform multiple sanity checks on the data generated"""

        self._check_heatmap_consistent('SentHeatMap', values, line_number)
        self._check_heatmap_consistent('ReceivedHeatMap', values, line_number)

        self._check_captured_consistent(values, line_number)

        self._check_latency_consistent(values, line_number)

    def _check_heatmap_consistent(self, heading, values, line_number):
        number_nodes = self._get_configuration().size()

        heatmap_index = self.headings.index(heading)
        heatmap = values[heatmap_index]

        if not isinstance(heatmap, dict):
            raise RuntimeError("Expected the heatmap {} to be a dict ({})".format(heading, repr(heatmap)))

         # Check that there aren't too many nodes
        if len(heatmap) > number_nodes:
            raise RuntimeError("There are too many nodes in this map {} called {}, when there should be {} maximum.".format(
                len(heatmap), heading, number_nodes))

        # Check that the node ids are in the right range
        #for k in heatmap.keys():
        #    if k < 0 or k >= number_nodes:
        #        raise RuntimeError("The key {} is invalid for this map it is not between {} and {}".format(k, 0, number_nodes))
    
    def _check_captured_consistent(self, values, line_number):
        """If captured is set to true, there should be an attacker at the source location"""
        captured_index = self.headings.index("Captured")
        captured = values[captured_index]

        attacker_distance_index = self.headings.index("AttackerDistance")
        attacker_distance = values[attacker_distance_index]

        # Handle two sorts of attacker distance dicts
        # 1. {attacker_id: distance}
        # 2. {(source_id, attacker_id): distance}}
        any_at_source = any(
            np.isclose(dist, 0.0) if isinstance(dist, Number) else any(np.isclose(v, 0.0) for (k, v) in dist.items())
            for dist
            in attacker_distance.values()
        )

        if captured != any_at_source:
            raise RuntimeError("There is a discrepancy between captured ({}) and the attacker distances {}.".format(
                captured, attacker_distance))

    def _check_latency_consistent(self, values, line_number):
        """Check NormalLatency is not 0"""
        latency_index = self.headings.index("NormalLatency")
        latency = values[latency_index]

        if math.isnan(latency):
            raise RuntimeError('The NormalLatency {} is a NaN'.format(latency))

        if latency <= 0:
            raise RuntimeError("The NormalLatency {} is less than or equal to 0.".format(latency))


    def detect_outlier(self, values):
        """Raise an exception in this function if an individual result should be
        excluded from the analysis"""
        pass

    def average_of(self, header):
        values = self.columns[header]

        first = values[0]

        if isinstance(first, dict):
            return self.dict_mean(values)
        elif isinstance(first, str):
            raise TypeError("Cannot find the average of a string for {}".format(header))
        else:
            return values.mean()

    def variance_of(self, header):
        values = self.columns[header]

        first = values[0]

        if isinstance(first, dict):
            raise NotImplementedError("Finding the variance of dicts is not implemented")
        elif isinstance(first, str):
            raise TypeError("Cannot find the variance of a string for {}".format(header))
        else:
            return values.var()

    def median_of(self, header):
        values = self.columns[header]

        first = values[0]

        if isinstance(first, dict):
            raise NotImplementedError("Finding the median of dicts is not implemented")
        elif isinstance(first, str):
            raise TypeError("Cannot find the median of a string for {}".format(header))
        else:
            return values.median()


    @staticmethod
    def dict_sum(dics):
        result = {}
        for d in dics:
            for (key, value) in d.items():
                if key not in result:
                    result[key] = value
                else:
                    result[key] += value
        return result

    @classmethod
    def dict_mean(cls, dict_list):

        result = {
            k: float(v) / len(dict_list)
            for (k, v)
            in cls.dict_sum(dict_list).items()
        }

        return result


class AnalysisResults:
    def __init__(self, analysis):
        self.average_of = {}
        self.variance_of = {}
        self.median_of = {}

        skip = ["Seed"]

        expected_fail = ['Collisions', "NodeWasSource"]

        for heading in analysis.headings:
            if heading in skip:
                continue

            try:
                self.average_of[heading] = analysis.average_of(heading)
            except NotImplementedError:
                pass
            except (TypeError, RuntimeError) as ex:
                if heading not in expected_fail:
                    print("Failed to average {}: {}".format(heading, ex), file=sys.stderr)
                    #print(traceback.format_exc(), file=sys.stderr)
            
            try:
                self.variance_of[heading] = analysis.variance_of(heading)
            except NotImplementedError:
                pass
            except (TypeError, RuntimeError) as ex:
                if heading not in expected_fail:
                    print("Failed to find variance {}: {}".format(heading, ex), file=sys.stderr)
                    #print(traceback.format_exc(), file=sys.stderr)

        self.median_of['TimeTaken'] = analysis.median_of('TimeTaken')

        self.opts = analysis.opts
        self.columns = analysis.columns

    def number_of_repeats(self):
        # Get a name of any of the columns
        aname = next(iter(self.columns))

        # Find the length of that list
        return len(self.columns[aname])

class AnalyzerCommon(object):
    def __init__(self, results_directory, values, normalised_values=None):
        self.results_directory = results_directory
        self.values = values
        self.normalised_values = normalised_values if normalised_values is not None else tuple()

    @staticmethod
    def common_results_header():
        d = OrderedDict()
        
        # Include the number of simulations that were analysed
        d['repeats']            = lambda x: str(x.number_of_repeats())

        # The options that all simulations must include
        # We do not loop though opts to allow algorithms to rename parameters if they wish
        for parameter in simulator.common.global_parameter_names:

            parameter_underscore = parameter.replace(" ", "_")

            d[parameter]        = lambda x, name=parameter_underscore: x.opts[name]

        return d

    @staticmethod
    def common_results(d):
        """These metrics are ones that all simulations should have.
        But this function doesn't need to be used if the metrics need special treatment."""

        d['sent']               = lambda x: AnalyzerCommon._format_results(x, 'Sent')
        d['received']           = lambda x: AnalyzerCommon._format_results(x, 'Received')
        d['delivered']          = lambda x: AnalyzerCommon._format_results(x, 'Delivered', allow_missing=True)

        d['time taken']         = lambda x: AnalyzerCommon._format_results(x, 'TimeTaken')
        d['wall time']          = lambda x: AnalyzerCommon._format_results(x, 'WallTime')
        d['event count']        = lambda x: AnalyzerCommon._format_results(x, 'EventCount')

    @staticmethod
    def _format_results(x, name, allow_missing=False, average_corrector=lambda x: x, variance_corrector=lambda x: x):
        if name in x.variance_of:
            ave = average_corrector(x.average_of[name])
            var = variance_corrector(x.variance_of[name])
            return "{}({})".format(ave, var)
        else:
            try:
                ave = average_corrector(x.average_of[name])
                return "{}".format(ave)
            except KeyError:
                if not allow_missing:
                    raise
                else:
                    return "None"

    def analyse_path(self, path):
        return Analyse(path, self.normalised_values)

    def analyse_and_summarise_path(self, path):
        return AnalysisResults(self.analyse_path(path))

    def run(self, summary_file):
        """Perform the analysis and write the output to the :summary_file:"""
        
        def worker(inqueue, outqueue):
            while True:
                item = inqueue.get()

                if item is None:
                    return

                path = item

                try:
                    result = self.analyse_and_summarise_path(path)

                    # Skip 0 length results
                    if result.number_of_repeats() == 0:
                        outqueue.put((path, None, "There are 0 repeats"))
                        continue

                    line = "|".join(fn(result) for fn in self.values.values())

                    outqueue.put((path, line, None))

                except Exception as e:
                    outqueue.put((path, None, e))


        nprocs = multiprocessing.cpu_count()

        inqueue = multiprocessing.Queue()
        outqueue = multiprocessing.Queue()

        pool = multiprocessing.Pool(nprocs, worker, (inqueue, outqueue))


        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process.
        # These are sorted to give anyone watching the output a sense of progress.
        files = sorted(fnmatch.filter(os.listdir(self.results_directory), '*.txt'))

        total = len(files)


        for infile in files:
            path = os.path.join(self.results_directory, infile)
            inqueue.put(path)

        # Push the queue sentinel
        for i in range(nprocs):
            inqueue.put(None)


        with open(summary_file_path, 'w') as out:

            print("|".join(self.values.keys()), file=out)

            start_time = timeit.default_timer()

            for num in range(total):
                (path, line, error) = outqueue.get()

                print('Analysing {0}'.format(path))

                if error is None:
                    print(line, file=out)
                else:
                    print("Error processing {} with {}".format(path, error))

                current_time_taken = timeit.default_timer() - start_time
                time_per_job = current_time_taken / (num + 1)
                estimated_total = time_per_job * total
                estimated_remaining = estimated_total - current_time_taken

                current_time_taken_str = str(datetime.timedelta(seconds=current_time_taken))
                estimated_remaining_str = str(datetime.timedelta(seconds=estimated_remaining))

                print("Finished analysing file {} out of {}. Done {}%. Time taken {}, estimated remaining {}".format(
                    num + 1, total, ((num + 1) / total) * 100.0, current_time_taken_str, estimated_remaining_str))
                print()

            print('Finished writing {}'.format(summary_file))

        inqueue.close()
        inqueue.join_thread()

        outqueue.close()
        outqueue.join_thread()

        pool.close()
        pool.join()
