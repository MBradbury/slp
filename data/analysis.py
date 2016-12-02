from __future__ import print_function, division

import ast
import base64
from collections import OrderedDict, Sequence
import copy
import fnmatch
from functools import partial
import gc
from itertools import islice
import math
import multiprocessing
from numbers import Number
import os
import re
import sys
import traceback
import zlib

from more_itertools import unique_everseen
import numpy as np
import pandas as pd
import psutil

from data.progress import Progress

import simulator.common
import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel

def bytes2human(num):
    """Converts a number of bytes to a human readable string
    # From: https://github.com/giampaolo/psutil/blob/master/scripts/meminfo.py
    # http://code.activestate.com/recipes/578019
    # >>> bytes2human(10000)
    # '9.8K'
    # >>> bytes2human(100001221)
    # '95.4M'"""
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, symb in enumerate(symbols):
        prefix[symb] = 1 << (i + 1) * 10
    for symb in reversed(symbols):
        if num >= prefix[symb]:
            value = float(num) / prefix[symb]
            return '%.1f%s' % (value, symb)
    return "%sB" % num

def pprint_ntuple(nt):
    """Returns a tuple of human readable bytes from a tuple of bytes
    # From: https://github.com/giampaolo/psutil/blob/master/scripts/meminfo.py"""
    result = {}
    for name in nt._fields:
        value = getattr(nt, name)
        if name != 'percent':
            result[name] = bytes2human(value)
    return nt._replace(**result)

def try_to_free_memory():
    """Call this function in an attempt to free any unfreed memory"""
    gc.collect()

    # See: https://github.com/pydata/pandas/issues/2659
    # Which discusses using malloc_trim, but was found to have little impact here.

class EmptyFileError(RuntimeError):
    def __init__(self, filename):
        super(EmptyFileError, self).__init__("The file '{}' is empty.".format(filename))

class EmptyDataFrameError(RuntimeError):
    def __init__(self, filename):
        super(EmptyDataFrameError, self).__init__("The DataFrame loaded from '{}' is empty.".format(filename))

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
    item = item.replace('inf', '2e308')

    return ast.literal_eval(item)

DICT_NODE_KEY_RE = re.compile(r'(\d+):\s*(\d+\.\d+|\d+)\s*(?:,|}$)')

def _parse_dict_node_to_value(indict, decompress=False):
    # Parse a dict like "{1: 10, 2: 20, 3: 40}"

    if decompress:
        indict = zlib.decompress(base64.b64decode(indict))

    result = {
        int(a): float(b)
        for (a, b) in DICT_NODE_KEY_RE.findall(indict)
    }

    # Reduces memory usage, but increases cpu time by a factor of 5 to create this
    #result = pd.Series(result, dtype=np.float_)

    # Direct parsing is also slow
    #result = pd.read_csv(
    #    StringIO.StringIO(indict[1:-1].replace(",", "\n")),
    #    squeeze=True,
    #    sep=":",
    #    header=None, names=("nid", "value"))

    return result

DICT_TUPLE_KEY_RE = re.compile(r'\((\d+),\s*(\d+)\):\s*(\d+\.\d+|\d+)\s*(?:,|}$)')
#DICT_TUPLE_KEY_OLD_RE = re.compile(r'(\d+):\s*(\d+\.\d+|\d+)\s*(?:,|}$)')

def _parse_dict_tuple_nodes_to_value(indict):
    # Parse a dict like "{(0, 1): 5, (0, 3): 20, (1, 1): 40}"
    # but also handle the old style of "{0: 1}"

    # Handle two sorts of attacker distance dicts
    # 1. {attacker_id: distance}
    # 2. {(source_id, attacker_id): distance}}

    # New style
    dict1 = {
        (int(a), int(b)): float(c)
        for (a, b, c) in DICT_TUPLE_KEY_RE.findall(indict)
    }

    # Old style - assume the source is 0
    #dict2 = {
    #    (0, int(b)): float(c)
    #    for (b, c) in DICT_TUPLE_KEY_OLD_RE.findall(indict)
    #}

    #dict1.update(dict2)

    return dict1

def dict_mean(dict_list):
    """Dict mean using incremental averaging"""

    result = dict_list[0]

    get = result.get

    for (n, dict_item) in enumerate(islice(dict_list, 1, None), start=2):
        for (key, value) in dict_item.iteritems():
            current = get(key, 0)
            result[key] = current + ((value - current) / n)

    return result

def dict_var(dict_list, mean):
    """Dict var using incremental calculation"""
    raise RuntimeError("Finding the variance of a dict is not implemented")

def _energy_impact(columns, cached_cols, constants):
    # Magic constants are from Great Duck Island paper, in nanoamp hours
    cost_per_bcast_nah = 20.0
    cost_per_deliver_nah = 8.0

    return (columns["Sent"] * cost_per_bcast_nah + columns["Received"] * cost_per_deliver_nah) / 1000000.0

def _daily_allowance_used(columns, cached_cols, constants):
    # Magic constants are from Great Duck Island paper
    daily_allowance_mah = 6.9

    cpu_power_consumption_ma = 5

    duty_cycle = 0.042

    daily_allowance_mah -= cpu_power_consumption_ma * 24 * duty_cycle

    energy_impact = cached_cols["energy_impact"]
    num_nodes = constants["num_nodes"]
    time_taken = columns["TimeTaken"]

    energy_impact_per_node_per_second = (energy_impact / num_nodes) / time_taken

    energy_impact_per_node_per_day_when_active = energy_impact_per_node_per_second * (60.0 * 60.0 * 24.0 * duty_cycle)

    return (energy_impact_per_node_per_day_when_active / daily_allowance_mah) * 100.0

def _get_calculation_columns():
    cols = {}

    cols["energy_impact"] = _energy_impact
    cols["daily_allowance_used"] = _daily_allowance_used

    return cols

class Analyse(object):

    HEADING_DTYPES = {
        "Seed": np.int64,
        "Sent": np.uint32,
        "Captured": np.bool_,
        "ReachedSimUpperBound": np.bool_,
        "Received": np.uint32,
        "Delivered": np.uint32,
        "ReceiveRatio": np.float_,
        "TimeTaken": np.float_,
        "WallTime": np.float_,
        "TotalWallTime": np.float_,
        "EventCount": np.int64,
        "NormalLatency": np.float_,
        "NormalSinkSourceHops": np.float_,
        "FirstNormalSentTime": np.float_,
        "TimeBinWidth": np.float_,
    }

    HEADING_CONVERTERS = {
        #"Collisions": ast.literal_eval,
        "SentHeatMap": partial(_parse_dict_node_to_value, decompress=True),
        "ReceivedHeatMap": partial(_parse_dict_node_to_value, decompress=True),
        "AttackerDistance": _parse_dict_tuple_nodes_to_value,
        "AttackerMoves": _parse_dict_node_to_value,
        "AttackerStepsAway": _parse_dict_tuple_nodes_to_value,
        "AttackerStepsTowards": _parse_dict_tuple_nodes_to_value,
        "AttackerSinkDistance": _parse_dict_tuple_nodes_to_value,
        "AttackerMinSourceDistance": _parse_dict_tuple_nodes_to_value,
        #"NodeWasSource": _inf_handling_literal_eval,

        "ReceivedFromCloserOrSameHops": _parse_dict_node_to_value,
        "ReceivedFromCloserOrSameMeters": _parse_dict_node_to_value,
        "ReceivedFromFurtherHops": _parse_dict_node_to_value,
        "ReceivedFromFurtherMeters": _parse_dict_node_to_value,

        "ReceivedFromCloserOrSameHopsFake": _parse_dict_node_to_value,
        "ReceivedFromCloserOrSameMetersFake": _parse_dict_node_to_value,
        "ReceivedFromFurtherHopsFake": _parse_dict_node_to_value,
        "ReceivedFromFurtherMetersFake": _parse_dict_node_to_value,

        "DeliveredFromCloserOrSameHops": _parse_dict_node_to_value,
        "DeliveredFromCloserOrSameMeters": _parse_dict_node_to_value,
        "DeliveredFromFurtherHops": _parse_dict_node_to_value,
        "DeliveredFromFurtherMeters": _parse_dict_node_to_value,
    }

    def __init__(self, infile_path, normalised_values, with_converters=True,
                 with_normalised=True, headers_to_skip=None, keep_if_hit_upper_time_bound=False):

        self.opts = {}
        self.headers_to_skip = headers_to_skip

        all_headings = []

        self.normalised_columns = None

        with open(infile_path, 'r') as infile:
            line_number = 0

            for line in infile:

                line_number += 1

                # We need to remove the new line at the end of the line
                line = line.strip()

                if line.startswith('@'):
                    # Skip the attributes that contain some extra info
                    continue

                elif len(all_headings) == 0 and '=' in line:
                    # We are reading the options so record them.
                    # Some option values will have an '=' in them so only split once.
                    opt = line.split('=', 1)

                    self.opts[opt[0]] = opt[1]

                elif line.startswith('#'):
                    # Read the headings
                    all_headings = line[1:].split('|')

                    break

        if line_number == 0:
            raise EmptyFileError(infile_path)

        self.unnormalised_headings = [
            heading for heading in all_headings
            if heading not in (tuple() if headers_to_skip is None else headers_to_skip)
        ]

        self._unnormalised_headings_count = len(self.unnormalised_headings)

        self.additional_normalised_headings = _normalised_value_names(normalised_values) if with_normalised else []

        self.headings = list(self.unnormalised_headings)
        self.headings.extend(self.additional_normalised_headings)

        converters = self.HEADING_CONVERTERS if with_converters else None

        # Work out dtypes for other sent messages
        self.HEADING_DTYPES.update({name: np.uint32 for name in self.unnormalised_headings if name.endswith('Sent')})

        print("Loading: ", self.unnormalised_headings)

        df = pd.read_csv(
            infile_path,
            names=all_headings, header=None,
            usecols=self.unnormalised_headings,
            sep='|',
            skiprows=line_number,
            comment='@',
            dtype=self.HEADING_DTYPES, converters=converters,
            compression=None,
            verbose=True
        )

        # Removes rows with infs in certain columns
        # If NormalLatency is inf then no Normal messages were ever received by a sink
        df = df.replace([np.inf, -np.inf], np.nan)
        df.dropna(subset=["NormalLatency"], how="all", inplace=True)

        if not keep_if_hit_upper_time_bound:
            print("Removing results that have hit the upper time bound...")

            indexes_to_remove = df[df["ReachedSimUpperBound"]].index
            df.drop(indexes_to_remove, inplace=True)

            print("Removed {} rows".format(len(indexes_to_remove)))

        # Remove any duplicated seeds. Their result will be the same so shouldn't be counted.
        duplicated_seeds_filter = df.duplicated(subset="Seed", keep=False)
        if not duplicated_seeds_filter.any():
            print("Removing the following duplicated seeds:")
            print(df["Seed"][duplicated_seeds_filter])

            print("Checking that duplicate seeds have the same results...")
            columns_to_check = ["Seed", "Sent", "Received", "Delivered", "Captured", "FirstNormalSentTime", "EventCount"]
            dupe_seeds = df[columns_to_check][duplicated_seeds_filter].groupby("Seed", sort=False)

            for name, group in dupe_seeds:
                differing = group[group.columns[group.apply(lambda s: len(s.unique()) > 1)]]

                if not differing.empty:
                    raise RuntimeError("For seed {}, the following columns differ: {}".format(name, differing))

            df.drop_duplicates(subset="Seed", keep="first", inplace=True)
        del duplicated_seeds_filter

        if len(df.index) == 0:
            raise EmptyDataFrameError(infile_path)

        if with_normalised:
            # Calculate any constants that do not change (e.g. from simulation options)
            constants = self._get_constants_from_opts()

            calc_cols = _get_calculation_columns()
            cached_cols = {}

            def get_cached_cal_cols(name):
                if name in cached_cols:
                    return cached_cols[name]

                cached_cols[name] = calc_cols[num](df, cached_cols, constants)

                return cached_cols[name]

            normalised_values_names = [(_normalised_value_name(num), _normalised_value_name(den)) for num, den in normalised_values]

            columns_to_add = OrderedDict()

            for (norm_head, (num, den)) in zip(self.additional_normalised_headings, normalised_values_names):

                if num in self.headings and den in self.headings:
                    print("Creating {} using ({},{}) on the fast path 1".format(norm_head, num, den))

                    num_col = columns_to_add[num] if num in columns_to_add else df[num]
                    den_col = columns_to_add[den] if den in columns_to_add else df[den]

                    columns_to_add[norm_head] = num_col / den_col

                elif num in self.headings and den in constants:
                    print("Creating {} using ({},{}) on the fast path 2".format(norm_head, num, den))

                    num_col = columns_to_add[num] if num in columns_to_add else df[num]

                    columns_to_add[norm_head] = num_col / constants[den]

                elif num in calc_cols and den in constants:
                    print("Creating {} using ({},{}) on the fast path 3".format(norm_head, num, den))

                    columns_to_add[norm_head] = get_cached_cal_cols(num) / constants[den]

                else:
                    print("Creating {} using ({},{}) on the slow path".format(norm_head, num, den))

                    #axis=1 means to apply per row
                    columns_to_add[norm_head] = df.apply(self._get_norm_value,
                                                         axis=1, raw=True, reduce=True,
                                                         args=(num, den, constants))

            if len(columns_to_add) > 0:
                print("Merging normalised columns with the loaded data...")
                self.normalised_columns = pd.concat(columns_to_add, axis=1, ignore_index=True, copy=False)
                self.normalised_columns.columns = list(columns_to_add.iterkeys())

        print("Columns:", df.info(memory_usage='deep'))

        if self.normalised_columns is not None:
            print("Normalised Columns:", self.normalised_columns.info(memory_usage='deep'))

        self.columns = df


    def headings_index(self, name):
        return self.headings.index(name)

    def _get_norm_value(self, row, num, den, constants):
        num_value = self._get_from_opts_or_values(num, row, constants)
        den_value = self._get_from_opts_or_values(den, row, constants)

        if num_value is None or den_value is None:
            return None

        return np.float_(num_value / den_value)


    def _get_configuration(self):
        return Configuration.create_specific(self.opts['configuration'],
                                             int(self.opts['network_size']),
                                             float(self.opts['distance']),
                                             self.opts['node_id_order'])

    def _get_constants_from_opts(self):
        """Get values that do not depend on the contents of the row."""
        constants = {}

        constants["1"] = 1
        constants["1.0"] = 1.0

        configuration = self._get_configuration()

        constants["num_nodes"] = configuration.size()
        constants["num_sources"] = len(configuration.source_ids)

        # Warning: This will only work for the FixedPeriodModel
        # All other models have variable source periods, so we cannot calculate this
        constants["source_period"] = float(SourcePeriodModel.eval_input(self.opts["source_period"]))
        constants["source_rate"] = 1.0 / constants["source_period"]
        constants["source_period_per_num_sources"] = constants["source_period"] / constants["num_sources"]
        constants["source_rate_per_num_sources"] = constants["source_rate"] / constants["num_sources"]

        return constants

    def _get_from_opts_or_values(self, name, values, constants):
        """Get either the row value for :name:, the constant of that name, or calculate the additional metric for that name."""
        try:
            index = self.headings.index(name)

            #print(name + " " + key + " " + str(values))

            return values[index]
        except ValueError:

            if name in constants:
                return constants[name]

            if name == "good_move_ratio":

                if __debug__:
                    attacker_moves = values[self.headings.index("AttackerMoves")]

                    # We can't calculate the good move ratio if the attacker hasn't moved
                    for (attacker_id, num_moves) in attacker_moves.iteritems():
                        if num_moves == 0:
                            print("Unable to calculate good_move_ratio due to the attacker {} not having moved for row {}.".format(attacker_id, values.name))
                            return None

                try:
                    steps_towards = values[self.headings.index("AttackerStepsTowards")]
                    steps_away = values[self.headings.index("AttackerStepsAway")]
                except ValueError as ex:
                    #print("Unable to calculate good_move_ratio due to the KeyError {}".format(ex))
                    return None

                ratios = []

                for key in steps_towards.keys():
                    steps_towards_node = steps_towards[key]
                    steps_away_from_node = steps_away[key]

                    ratios.append(steps_towards_node / (steps_towards_node + steps_away_from_node))

                ave = np.mean(ratios)

                return ave

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
        # TODO: Call this
        pass

    def average_of(self, header):
        values = (self.columns if header in self.columns else self.normalised_columns)[header]

        first = values[0]

        if isinstance(first, dict):
            return dict_mean(values)
        elif isinstance(first, str):
            raise TypeError("Cannot find the average of a string for {}".format(header))
        else:
            return values.mean()

    def variance_of(self, header, mean):
        values = (self.columns if header in self.columns else self.normalised_columns)[header]

        first = values[0]

        if isinstance(first, dict):
            return dict_var(values, mean)
        elif isinstance(first, str):
            raise TypeError("Cannot find the variance of a string for {}".format(header))
        else:
            return values.var()

    def median_of(self, header):
        values = (self.columns if header in self.columns else self.normalised_columns)[header]

        first = values[0]

        if isinstance(first, dict):
            raise NotImplementedError("Finding the median of dicts is not implemented")
        elif isinstance(first, str):
            raise TypeError("Cannot find the median of a string for {}".format(header))
        else:
            return values.median()


class AnalysisResults(object):
    def __init__(self, analysis):
        self.average_of = {}
        self.variance_of = {}
        self.median_of = {}

        skip = ["Seed"]

        expected_fail = ['Collisions', "NodeWasSource", "AttackerMovesInResponseTo", "SentOverTime"]

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
                self.variance_of[heading] = analysis.variance_of(heading, self.average_of[heading])
            except NotImplementedError:
                pass
            except (TypeError, RuntimeError) as ex:
                if heading not in expected_fail:
                    print("Failed to find variance {}: {}".format(heading, ex), file=sys.stderr)
                    #print(traceback.format_exc(), file=sys.stderr)

        self.median_of['TimeTaken'] = analysis.median_of('TimeTaken')

        self.opts = analysis.opts
        self.headers_to_skip = analysis.headers_to_skip
        
        self.number_of_repeats = analysis.columns.shape[0]

    def get_configuration(self):
        return Configuration.create_specific(self.opts['configuration'],
                                             int(self.opts['network_size']),
                                             float(self.opts['distance']),
                                             self.opts['node_id_order'])

class AnalyzerCommon(object):
    def __init__(self, results_directory, values, normalised_values=None):
        self.results_directory = results_directory
        self.values = values
        self.normalised_values = normalised_values if normalised_values is not None else tuple()

    @staticmethod
    def common_results_header(local_parameter_names):
        d = OrderedDict()
        
        # Include the number of simulations that were analysed
        d['repeats']            = lambda x: str(x.number_of_repeats)

        # Give everyone access to the number of nodes in the simulation
        d['num nodes']          = lambda x: str(x.get_configuration().size())

        # The options that all simulations must include and the local parameter names
        for parameter in simulator.common.global_parameter_names + local_parameter_names:

            param_underscore = parameter.replace(" ", "_")

            d[parameter]        = lambda x, name=param_underscore: x.opts[name]

        return d

    @staticmethod
    def common_results(d):
        """These metrics are ones that all simulations should have.
        But this function doesn't need to be used if the metrics need special treatment."""

        d['sent']               = lambda x: AnalyzerCommon._format_results(x, 'Sent')
        d['received']           = lambda x: AnalyzerCommon._format_results(x, 'Received')
        d['delivered']          = lambda x: AnalyzerCommon._format_results(x, 'Delivered')

        d['time taken']         = lambda x: AnalyzerCommon._format_results(x, 'TimeTaken')
        d['time taken median']  = lambda x: str(x.median_of['TimeTaken'])
        
        d['total wall time']    = lambda x: AnalyzerCommon._format_results(x, 'TotalWallTime')
        d['wall time']          = lambda x: AnalyzerCommon._format_results(x, 'WallTime')
        d['event count']        = lambda x: AnalyzerCommon._format_results(x, 'EventCount')

        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['reached upper bound']= lambda x: str(x.average_of['ReachedSimUpperBound'])

        d['received ratio']     = lambda x: AnalyzerCommon._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: AnalyzerCommon._format_results(x, 'NormalLatency')
        d['ssd']                = lambda x: AnalyzerCommon._format_results(x, 'NormalSinkSourceHops')

        d['attacker moves']     = lambda x: AnalyzerCommon._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: AnalyzerCommon._format_results(x, 'AttackerDistance')
        

    @staticmethod
    def _format_results(x, name, allow_missing=False, average_corrector=None, variance_corrector=None):
        if name in x.variance_of:
            ave = x.average_of[name]
            var = x.variance_of[name]

            if average_corrector is not None:
                ave = average_corrector(ave)

            if variance_corrector is not None:
                var = variance_corrector(var)

            return "{}({})".format(ave, var)
        else:
            try:
                ave = x.average_of[name]

                if average_corrector is not None:
                    ave = average_corrector(ave)

                return str(ave)
            except KeyError:
                if allow_missing or name in x.headers_to_skip:
                    return "None"
                else:
                    raise

    def analyse_path(self, path, **kwargs):
        #try:
        return Analyse(path, self.normalised_values, **kwargs)
        #except Exception as ex:
        #    raise RuntimeError("Error analysing {}".format(path), ex)

    def analyse_and_summarise_path(self, path, **kwargs):
        return AnalysisResults(self.analyse_path(path, **kwargs))

    def analyse_and_summarise_path_wrapped(self, path, **kwargs):
        """Calls analyse_and_summarise_path, but wrapped inside a Process.
        This forces memory allocated during the analysis to be freed."""
        def wrapped(queue, path, **kwargs):
            queue.put(self.analyse_and_summarise_path(path, **kwargs))

            print("Memory usage of worker:", pprint_ntuple(psutil.Process().memory_full_info()))

        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=wrapped, args=(q, path), kwargs=kwargs)
        p.start()
        result = q.get()

        p.join()

        return result

    def run(self, summary_file, nprocs=None, **kwargs):
        """Perform the analysis and write the output to the :summary_file:.
        If :nprocs: is not specified then the number of CPU cores will be used.
        """

        # Skip the overhead of the queue with 1 process.
        # This also allows easy profiling
        if nprocs is not None and nprocs == 1:
            return self.run_single(summary_file, **kwargs)

        def worker(inqueue, outqueue):
            while True:
                item = inqueue.get()

                if item is None:
                    return

                path = item

                try:
                    result = self.analyse_and_summarise_path(path, **kwargs)

                    # Skip 0 length results
                    if result.number_of_repeats == 0:
                        outqueue.put((path, None, "There are 0 repeats"))
                        continue

                    line = "|".join(fn(result) for fn in self.values.values())

                    # Try to force a cleanup of the memory
                    result = None

                    outqueue.put((path, line, None))

                    # Try to recover some memory
                    try_to_free_memory()

                except Exception as ex:
                    outqueue.put((path, None, (ex, traceback.format_exc())))

        if nprocs is None:
            nprocs = multiprocessing.cpu_count()

            print("Using {} threads".format(nprocs))

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

            progress = Progress("analysing file")
            progress.start(len(files))

            for num in range(total):
                (path, line, error) = outqueue.get()

                print('Analysing {0}'.format(path))

                if error is None:
                    print(line, file=out)
                else:
                    (ex, tb) = error
                    print("Error processing {} with {}".format(path, ex))
                    print(tb)

                progress.print_progress(num)

            print('Finished writing {}'.format(summary_file))

        inqueue.close()
        inqueue.join_thread()

        outqueue.close()
        outqueue.join_thread()

        pool.close()
        pool.join()

    def run_single(self, summary_file, **kwargs):
        """Perform the analysis and write the output to the :summary_file:"""
        
        def worker(ipath):
            result = self.analyse_and_summarise_path_wrapped(path, **kwargs)

            # Skip 0 length results
            if result.number_of_repeats == 0:
                raise RuntimeError("There are 0 repeats.")

            line = "|".join(fn(result) for fn in self.values.values())

            # Try to force a cleanup of the memory
            result = None

            # Try to recover some memory
            try_to_free_memory()

            return line

        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process.
        # These are sorted to give anyone watching the output a sense of progress.
        files = sorted(fnmatch.filter(os.listdir(self.results_directory), '*.txt'))

        with open(summary_file_path, 'w') as out:

            print("|".join(self.values.keys()), file=out)

            progress = Progress("analysing file")
            progress.start(len(files))

            for num, infile in enumerate(files):
                path = os.path.join(self.results_directory, infile)

                print('Analysing {0}'.format(path))

                try:
                    line = worker(path)

                    print(line, file=out)
                except Exception as ex:
                    print("Error processing {} with {}".format(path, ex))
                    print(traceback.format_exc())

                progress.print_progress(num)

            print('Finished writing {}'.format(summary_file))
