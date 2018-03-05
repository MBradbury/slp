
import ast
import base64
from collections import OrderedDict, Sequence
from functools import partial
import gc
from itertools import islice
import math
import multiprocessing
from numbers import Number
import os
import pickle
import re
import sys
import traceback
import zlib

from more_itertools import unique_everseen, one
import numpy as np
import pandas as pd
import psutil

import data.submodule_loader as submodule_loader
from data.progress import Progress

import simulator.sim
import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel
from simulator.Topology import TopologyId

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
        super(EmptyFileError, self).__init__(f"The file '{filename}' is empty.")

class EmptyDataFrameError(RuntimeError):
    def __init__(self, filename):
        super(EmptyDataFrameError, self).__init__(f"The DataFrame loaded from '{filename}' is empty.")

def _normalised_value_name(value, prefix):
    if isinstance(value, str):
        return value
    elif isinstance(value, Sequence) and len(value) == 2:
        return "{}({},{})".format(prefix, _normalised_value_name(value[0], prefix), _normalised_value_name(value[1], prefix))
    else:
        raise RuntimeError("Unknown type or length for value '{}' of type {}".format(value, type(value)))

def _dfs_names(value, prefix):
    result = []

    if isinstance(value, str):
        #result.append(value)
        pass
    elif isinstance(value, Sequence) and len(value) == 2:
        result.extend(_dfs_names(value[0], prefix))
        result.extend(_dfs_names(value[1], prefix))
        result.append(_normalised_value_name(value, prefix))
    else:
        raise RuntimeError("Unknown type or length for value '{}' of type {}".format(value, type(value)))

    return result

def _normalised_value_names(values, prefix):
    all_results = []

    for value in values:
        all_results.extend(_dfs_names(value, prefix))

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
        indict = zlib.decompress(base64.b64decode(indict)).decode("utf-8")

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

def _parse_dict_tuple_nodes_to_value(indict):
    """Parse a dict like "{(0, 1): 5, (0, 3): 20, (1, 1): 40}"
    where the structure is {(source_id, attacker_id): distance}"""

    dict1 = {
        (int(a), int(b)): float(c)
        for (a, b, c) in DICT_TUPLE_KEY_RE.findall(indict)
    }

    return dict1

DICT_STRING_TUPLE_KEY_RE = re.compile(r"\('([^']+)',\s*'([^']+)'\):\s*(\d+\.\d+|\d+)\s*(?:,|}$)")

def _parse_dict_string_tuple_to_value(indict):

    dict1 = {
        (a, b): float(c)
        for (a, b, c) in DICT_STRING_TUPLE_KEY_RE.findall(indict)
    }

    return dict1

def dict_mean(dict_list):
    """Dict mean using incremental averaging"""

    result = dict(next(iter(dict_list)))

    get = result.get

    for (n, dict_item) in enumerate(islice(dict_list, 1, None), start=2):
        for (key, value) in dict_item.items():
            current = get(key, 0)
            result[key] = current + ((value - current) / n)

    return result

def dict_var(dict_list, mean):
    """Dict variance"""

    first = next(iter(dict_list))

    lin = {k: [] for k in first}

    for d in islice(dict_list, 1, None):
        for (k, v) in d.items():
            lin[k].append(v)

    for k in lin:
        lin[k] = np.var(lin[k], dtype=np.float64)

    return lin

"""
def _energy_impact(columns, cached_cols, constants):
    # Magic constants are from Great Duck Island paper, in nanoamp hours
    cost_per_bcast_nah = 20.0
    cost_per_deliver_nah = 8.0

    # Convert to mAh in result
    return (columns["Sent"] * cost_per_bcast_nah + columns["Delivered"] * cost_per_deliver_nah) / 1000000.0

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
"""

def _time_after_first_normal(columns, cached_cols, constants):
    return columns["TimeTaken"] - columns["FirstNormalSentTime"]

def _attacker_distance_wrt_src(columns, cached_cols, constants):
    # TODO: Not going to work well for multiple sinks
    # TODO: assumes the attacker starts at the sink

    return columns["AttackerDistance"].apply(lambda x: {
        (source_id, attacker_id): dist - one(ssd)
        for ((source_id, attacker_id), dist) in x.items()
        for ssd in [ssd for ((sink, src), ssd) in constants["ssds"].items() if src == source_id]
    })

def _average_duty_cycle(columns, cached_cols, constants):
    t2o = constants["configuration"].topology.t2o

    return columns["DutyCycle"].apply(lambda x:
        np.mean([d for (nid, d) in x.items() if t2o(TopologyId(nid)) not in constants["configuration"].sink_ids])
    )

def _get_calculation_columns():
    return {
        #"energy_impact": _energy_impact,
        #"daily_allowance_used": _daily_allowance_used,
        "time_after_first_normal": _time_after_first_normal,

        "attacker_distance_wrt_src": _attacker_distance_wrt_src,

        "average_duty_cycle": _average_duty_cycle,
    }

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
        "MemoryRSS": np.uint64,
        "MemoryVMS": np.uint64,
        "NormalLatency": np.float_,
        "NormalSinkSourceHops": np.float_,
        "FirstNormalSentTime": np.float_,
        "TimeBinWidth": np.float_,
        "FailedRtx": np.uint32,
        "TotalParentChanges": np.uint32,
        "TFS": np.uint32,
        "PFS": np.uint32,
        "TailFS": np.uint32,
        "FakeToNormal": np.uint32,
        "FakeToFake": np.uint32,
        "FakeNodesAtEnd": np.uint32,
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
        "AttackerReceiveRatio": partial(_parse_dict_node_to_value, decompress=False),
        #"NodeWasSource": _inf_handling_literal_eval,

        "NodeTransitions": _parse_dict_string_tuple_to_value,
        "Errors": _parse_dict_node_to_value,

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

        "ParentChangeHeatMap": partial(_parse_dict_node_to_value, decompress=True),

        # Can be None if MetricsCommon.num_normal_sent_if_finished is nan
        "FailedAvoidSink": lambda x: np.float_('NaN') if x == "None" else np.float_(x),

        "DutyCycleStart": lambda x: None if x == "None" else np.float_(x), # Either None or float
        "DutyCycle": _parse_dict_node_to_value,
    }

    def __init__(self, infile_path, normalised_values, filtered_values, with_converters=True,
                 with_normalised=True, headers_to_skip=None, keep_if_hit_upper_time_bound=False,
                 verify_seeds=True):

        self.attributes = {}
        self.opts = {}

        all_headings = []

        self.normalised_columns = None

        with open(infile_path, 'r') as infile:
            line_number = 0
            hash_line_number = None

            for line in infile:

                line_number += 1

                # We need to remove the new line at the end of the line
                line = line.strip()

                # If we have found the # line
                if len(all_headings) != 0:
                    if line.startswith('@'):
                        raise RuntimeError(f"Multiple sets of metadata in {infile_path}")
                    else:
                        break

                if line.startswith('@'):
                    # The attributes that contain some extra info

                    k, v = line[1:].split(":", 1)

                    self.attributes[k] = v

                elif len(all_headings) == 0 and '=' in line:
                    # We are reading the options so record them.
                    # Some option values will have an '=' in them so only split once.
                    opt = line.split('=', 1)

                    self.opts[opt[0]] = opt[1]

                elif line.startswith('#'):
                    # Read the headings
                    all_headings = line[1:].split('|')
                    hash_line_number = line_number

        if line_number == 0 or line_number == hash_line_number:
            raise EmptyFileError(infile_path)

        self.headers_to_skip = {header for header in all_headings if self._should_skip(header, headers_to_skip)}

        self.unnormalised_headings = [
            heading for heading in all_headings
            if heading not in self.headers_to_skip
        ]

        self._unnormalised_headings_count = len(self.unnormalised_headings)

        self.additional_normalised_headings = _normalised_value_names(normalised_values, "norm") if with_normalised else []
        self.additional_filtered_headings = _normalised_value_names(filtered_values, "filtered") if with_normalised else []

        self.headings = list(self.unnormalised_headings)
        self.headings.extend(self.additional_normalised_headings)
        self.headings.extend(self.additional_filtered_headings)

        converters = self.HEADING_CONVERTERS if with_converters else None

        # Work out dtypes for other sent messages
        self.HEADING_DTYPES.update({name: np.uint32 for name in self.unnormalised_headings if name.endswith('Sent')})

        print("Loading: ", self.unnormalised_headings)

        df = pd.read_csv(
            infile_path,
            names=all_headings, header=None,
            usecols=self.unnormalised_headings,
            sep='|',
            skiprows=line_number - 1,
            comment='@',
            dtype=self.HEADING_DTYPES, converters=converters,
            compression=None,
            verbose=True,
        )

        initial_length = len(df.index)

        if initial_length == 0:
            raise EmptyDataFrameError(infile_path)

        # Removes rows with infs in certain columns
        # If NormalLatency is inf then no Normal messages were ever received by a sink
        # If FirstNormalSentTime is nan then no messages were ever sent by a source
        df = df.replace([np.inf, -np.inf], np.nan)
        df.dropna(subset=("NormalLatency", "FirstNormalSentTime"), how="any", inplace=True)

        current_length = len(df.index)

        self.removed_rows_due_to_no_sink_delivery_count = initial_length - current_length

        print("Removed {} out of {} rows as no Normal message was ever received at the sink".format(
            self.removed_rows_due_to_no_sink_delivery_count, initial_length))

        if current_length == 0:
            raise RuntimeError("When removing results where the sink never received a Normal message, all results were removed.")

        if not keep_if_hit_upper_time_bound:
            print("Removing results that have hit the upper time bound...")

            indexes_to_remove = df[df["ReachedSimUpperBound"]].index
            df.drop(indexes_to_remove, inplace=True)

            self.removed_rows_due_to_upper_bound = len(indexes_to_remove)

            print("Removed {} out of {} rows that reached the simulation upper time bound".format(
                self.removed_rows_due_to_upper_bound, current_length))
        else:
            self.removed_rows_due_to_upper_bound = 0

        # Remove any duplicated seeds. Their result will be the same so shouldn't be counted.
        if verify_seeds:
            duplicated_seeds_filter = df.duplicated(subset="Seed", keep=False)
            if duplicated_seeds_filter.any():
                print("Removing the following duplicated seeds:")
                print(df["Seed"][duplicated_seeds_filter])

                print("Checking that duplicate seeds have the same results...")
                columns_to_check = ["Seed", "Sent", "Received", "Delivered", "Captured", "FirstNormalSentTime", "EventCount"]
                dupe_seeds = df[columns_to_check][duplicated_seeds_filter].groupby("Seed", sort=False)

                dupe_differing_seeds = {}

                for name, group in dupe_seeds:
                    differing = group[group.columns[group.apply(lambda s: len(s.unique()) > 1)]]

                    if not differing.empty:
                        dupe_differing_seeds[name] = differing

                if len(dupe_differing_seeds) > 0:
                    for name, differing in dupe_differing_seeds.items():
                        print(f"For seed {name} the following items differed:")
                        print(differing)

                    raise RuntimeError(f"For seeds {list(dupe_differing_seeds.keys())} different values were obtained")

                initial_length = len(df.index)

                df.drop_duplicates(subset="Seed", keep="first", inplace=True)

                current_length = len(df.index)

                self.removed_rows_due_to_duplicates = initial_length - current_length

                print("Removed {} out of {} rows as the seeds were duplicated".format(
                    self.removed_rows_due_to_duplicates, initial_length))
            else:
                self.removed_rows_due_to_duplicates = 0

            del duplicated_seeds_filter
        else:
            self.removed_rows_due_to_duplicates = 0

        if len(df.index) == 0:
            raise EmptyDataFrameError(infile_path)

        self.filtered_columns = {}

        if with_normalised:
            # Calculate any constants that do not change (e.g. from simulation options)
            constants = self._get_constants_from_opts()

            calc_cols = _get_calculation_columns()
            cached_cols = {}

            def get_cached_calc_cols(name):
                if name in cached_cols:
                    return cached_cols[name]

                cached_cols[name] = calc_cols[num](df, cached_cols, constants)

                return cached_cols[name]

            normalised_values_names = [
                (_normalised_value_name(num, "norm"), _normalised_value_name(den, "norm"))
                for num, den
                in normalised_values
            ]

            columns_to_add = OrderedDict()

            for (norm_head, (num, den)) in zip(self.additional_normalised_headings, normalised_values_names):

                if num in self.headings and den in self.headings:
                    print(f"Creating {norm_head} using ({num},{den}) on the fast path n1")

                    num_col = columns_to_add[num] if num in columns_to_add else df[num]
                    den_col = columns_to_add[den] if den in columns_to_add else df[den]

                    columns_to_add[norm_head] = num_col / den_col

                elif num in self.headings and den in constants:
                    print(f"Creating {norm_head} using ({num},{den}) on the fast path n2")

                    num_col = columns_to_add[num] if num in columns_to_add else df[num]

                    columns_to_add[norm_head] = num_col if den == "1" else num_col / constants[den]

                elif num in calc_cols and den in constants:
                    print(f"Creating {norm_head} using ({num},{den}) on the fast path n3")

                    num_col = get_cached_calc_cols(num)

                    columns_to_add[norm_head] = num_col if den == "1" else num_col / constants[den]

                else:
                    print(f"Creating {norm_head} using ({num},{den}) on the slow path ns")

                    #axis=1 means to apply per row
                    columns_to_add[norm_head] = df.apply(self._get_norm_value,
                                                         axis=1, raw=True, reduce=True,
                                                         args=(num, den, constants))


            filtered_values_names = [
                (_normalised_value_name(num, "filtered"), _normalised_value_name(den, "filtered"))
                for num, den
                in filtered_values
            ]

            for (filtered_head, (num, den)) in zip(self.additional_filtered_headings, filtered_values_names):
                
                if num in self.headings and den in df:
                    print(f"Creating {filtered_head} using ({num},{den}) on the fast path f1")

                    num_col = columns_to_add[num] if num in columns_to_add else df[num]
                    den_col = df[den]

                    self.filtered_columns[filtered_head] = num_col[den_col]

                else:
                    raise RuntimeError(f"Don't know how to calculate {filtered_head}")

            if len(columns_to_add) > 0:
                print("Merging normalised columns with the loaded data...")
                self.normalised_columns = pd.DataFrame.from_dict(columns_to_add)

        print("Columns:", df.info(memory_usage='deep'))

        if self.normalised_columns is not None:
            print("Normalised Columns:", self.normalised_columns.info(memory_usage='deep'))

        self.columns = df

    def sim_name(self):
        """The sim used to gather these results"""
        return self.attributes["sim"]


    def headings_index(self, name):
        return self.headings.index(name)

    def _should_skip(self, heading_name, headers_to_skip):
        if headers_to_skip is None:
            return False
        return any(re.fullmatch(to_skip, heading_name) is not None for to_skip in headers_to_skip)

    def _get_norm_value(self, row, num, den, constants):
        num_value = self._get_from_opts_or_values(num, row, constants)
        den_value = self._get_from_opts_or_values(den, row, constants)

        if num_value is None or den_value is None:
            return None

        return np.float_(num_value / den_value)


    def _get_configuration(self):
        arg_converters = {
            'network_size': int,
            'distance': float,
        }

        arg_values = {
            name.replace("_", " "): converter(self.opts[name])
            for (name, converter) in arg_converters.items()
            if name in self.opts
        }

        # Will never have a seed because opts to too early to get the
        # per simulation seed
        arg_values['seed'] = None

        # As we don't have a seed the node_id_order must always be topology
        arg_values['node id order'] = "topology"

        return Configuration.create(self.opts['configuration'], arg_values)

    def _get_constants_from_opts(self):
        """Get values that do not depend on the contents of the row."""
        constants = {}

        constants["1"] = 1
        constants["1.0"] = 1.0

        configuration = self._get_configuration()

        constants["configuration"] = configuration

        constants["num_nodes"] = configuration.size()
        constants["num_sources"] = len(configuration.source_ids)

        o2t = configuration.topology.o2t

        constants["ssds"] = {
            (o2t(sink), o2t(source)): configuration.ssd_meters(sink, source)
            for sink in configuration.sink_ids
            for source in configuration.source_ids
        }

        # Warning: This will only work for the FixedPeriodModel
        # All other models have variable source periods, so we cannot calculate this
        constants["source_period"] = float(SourcePeriodModel.eval_input(self.opts["source_period"]))
        constants["source_rate"] = 1.0 / constants["source_period"]
        constants["source_period_per_num_sources"] = constants["source_period"] / constants["num_sources"]
        constants["source_rate_per_num_sources"] = constants["source_rate"] / constants["num_sources"]

        return constants

    def _get_good_move_ratio(self, name, values, constants):
        if __debug__:
            attacker_moves = values[self.headings.index("AttackerMoves")]

            # We can't calculate the good move ratio if the attacker hasn't moved
            for (attacker_id, num_moves) in attacker_moves.items():
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

    def _get_from_opts_or_values(self, name, values, constants):
        """Get either the row value for :name:, the constant of that name, or calculate the additional metric for that name."""
        try:
            index = self.headings.index(name)
            return values[index]
        except ValueError:
            pass

        try:
            return constants[name]
        except KeyError:
            pass

        if name == "good_move_ratio":
            return self._get_good_move_ratio(name, values, constants)

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
            raise RuntimeError(f"Expected the heatmap {heading} to be a dict ({heatmap!r})")

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
            raise RuntimeError(f'The NormalLatency {latency} is a NaN')

        if latency <= 0:
            raise RuntimeError(f"The NormalLatency {latency} is less than or equal to 0.")


    def detect_outlier(self, values):
        """Raise an exception in this function if an individual result should be
        excluded from the analysis"""
        # TODO: Call this
        pass

    def find_column(self, header):
        try:
            return self.columns[header]
        except KeyError:
            pass

        try:
            return self.normalised_columns[header]
        except KeyError:
            pass

        try:
            return self.filtered_columns[header]
        except KeyError:
            pass

        raise KeyError(f"Unable to find {header}")

    def average_of(self, header):
        values = self.find_column(header)

        if len(values) == 0:
            # Filtered values may legitimately have no values
            if header.startswith("filtered"):
                return 0
            else:
                raise RuntimeError(f"There are no values for {header} to be able to average")

        first = next(iter(values))

        if isinstance(first, dict):
            return dict_mean(values)
        elif isinstance(first, str):
            raise TypeError(f"Cannot find the average of a string for {header}")
        else:
            return values.mean()

    def variance_of(self, header, mean):
        values = self.find_column(header)

        if len(values) == 0:
            # Filtered values may legitimately have no values
            if header.startswith("filtered"):
                return 0
            else:
                raise RuntimeError(f"There are no values for {header} to be able to find the variance")

        first = next(iter(values))

        if isinstance(first, dict):
            return dict_var(values, mean)
        elif isinstance(first, str):
            raise TypeError(f"Cannot find the variance of a string for {header}")
        else:
            return values.var()

    def median_of(self, header):
        values = self.find_column(header)

        if len(values) == 0:
            # Filtered values may legitimately have no values
            if header.startswith("filtered"):
                return None
            else:
                raise RuntimeError(f"There are no values for {header} to be able to find the median")

        first = next(iter(values))

        if isinstance(first, dict):
            raise NotImplementedError("Finding the median of dicts is not implemented")
        elif isinstance(first, str):
            raise TypeError(f"Cannot find the median of a string for {header}")
        else:
            return values.median()


class AnalysisResults(object):
    def __init__(self, analysis):
        self.average_of = {}
        self.variance_of = {}
        #self.median_of = {}

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
            except (TypeError, KeyError, RuntimeError) as ex:
                if heading not in expected_fail:
                    print("Failed to find variance {}: {}".format(heading, ex), file=sys.stderr)
                    #print(traceback.format_exc(), file=sys.stderr)

        #self.median_of['TimeTaken'] = analysis.median_of('TimeTaken')

        self.opts = analysis.opts
        self.headers_to_skip = analysis.headers_to_skip
        
        self.number_of_repeats = analysis.columns.shape[0]

        self.dropped_hit_upper_bound = analysis.removed_rows_due_to_upper_bound
        self.dropped_no_sink_delivery = analysis.removed_rows_due_to_no_sink_delivery_count
        self.dropped_duplicates = analysis.removed_rows_due_to_duplicates

        self.configuration = analysis._get_configuration()

class AnalyzerCommon(object):
    def __init__(self, sim_name, results_directory):
        self.sim_name = sim_name
        self.results_directory = results_directory
        
        self.normalised_values = self.normalised_parameters()
        self.normalised_values += (('time_after_first_normal', '1'),)# ('attacker_distance_wrt_src', '1'))

        self.filtered_values = self.filtered_parameters()

        self.values = self.results_header()

        self.values['dropped no sink delivery'] = lambda x: str(x.dropped_no_sink_delivery)
        self.values['dropped hit upper bound']  = lambda x: str(x.dropped_hit_upper_bound)
        self.values['dropped duplicates']       = lambda x: str(x.dropped_duplicates)

    def common_results_header(self, local_parameter_names):
        d = OrderedDict()
        
        # Include the number of simulations that were analysed
        d['repeats']            = lambda x: str(x.number_of_repeats)

        # Give everyone access to the number of nodes in the simulation
        d['num nodes']          = lambda x: str(x.configuration.size())

        sim = submodule_loader.load(simulator.sim, self.sim_name)

        # The options that all simulations must include and the local parameter names
        for parameter in sim.global_parameter_names + local_parameter_names:

            param_underscore = parameter.replace(" ", "_")

            d[parameter]        = lambda x, name=param_underscore: x.opts[name]

        return d

    def common_results(self, d):
        """These metrics are ones that all simulations should have.
        But this function doesn't need to be used if the metrics need special treatment."""

        d['sent']               = lambda x: self._format_results(x, 'Sent')
        d['received']           = lambda x: self._format_results(x, 'Received')
        d['delivered']          = lambda x: self._format_results(x, 'Delivered')

        d['time taken']         = lambda x: self._format_results(x, 'TimeTaken')
        #d['time taken median']  = lambda x: str(x.median_of['TimeTaken'])

        d['first normal sent time']= lambda x: self._format_results(x, 'FirstNormalSentTime')
        d['time after first normal']= lambda x: self._format_results(x, 'norm(time_after_first_normal,1)')
        
        # Metrics used for profiling simulation
        d['total wall time']    = lambda x: self._format_results(x, 'TotalWallTime')
        d['wall time']          = lambda x: self._format_results(x, 'WallTime')
        d['event count']        = lambda x: self._format_results(x, 'EventCount')
        d['memory rss']         = lambda x: self._format_results(x, 'MemoryRSS', allow_missing=True)
        d['memory vms']         = lambda x: self._format_results(x, 'MemoryVMS', allow_missing=True)

        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['reached upper bound']= lambda x: str(x.average_of['ReachedSimUpperBound'])

        d['received ratio']     = lambda x: self._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: self._format_results(x, 'NormalLatency')
        d['ssd']                = lambda x: self._format_results(x, 'NormalSinkSourceHops')
        
        d['unique normal generated']= lambda x: self._format_results(x, 'UniqueNormalGenerated', allow_missing=True)

        d['attacker moves']     = lambda x: self._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: self._format_results(x, 'AttackerDistance')
        #d['attacker distance wrt src']  = lambda x: self._format_results(x, 'norm(attacker_distance_wrt_src,1)')

        d['errors']             = lambda x: self._format_results(x, 'Errors', allow_missing=True)

    def results_header(self):
        raise NotImplementedError()

    def normalised_parameters(self):
        return []

    def filtered_parameters(self):
        return []


    @staticmethod
    def _format_results(x, name, allow_missing=False):
        if name in x.variance_of:
            ave = x.average_of[name]
            var = x.variance_of[name]

            #if isinstance(ave, dict):
            #    std = {k: math.sqrt(v) for (k, v) in var.items()}
            #    stderr = {k: v / math.sqrt(x.number_of_repeats) for (k, v) in std.items()}
            #else:
            #    std = math.sqrt(var)
            #    stderr = std / math.sqrt(x.number_of_repeats)

            return f"{ave};{var}"
        else:
            try:
                ave = x.average_of[name]

                return str(ave)
            except KeyError:
                if allow_missing or name in x.headers_to_skip:
                    return "None"
                else:
                    raise

    def analyse_path(self, path, **kwargs):
        return Analyse(path, self.normalised_values, self.filtered_values, **kwargs)

    def analyse_and_summarise_path(self, path, flush, **kwargs):
        pickle_path = path.rsplit(".", 1)[0] + ".pickle"

        result_file_create_time = os.path.getmtime(path)

        try:
            pickle_file_create_time = os.path.getmtime(pickle_path)
        except OSError:
            pickle_file_create_time = 0

        result = None

        if result_file_create_time < pickle_file_create_time and not flush:
            with open(pickle_path, 'rb') as pickle_file:
                saved_kwargs = pickle.load(pickle_file)

                if saved_kwargs == kwargs:
                    result = pickle.load(pickle_file)
                    print(f"Loaded result from pickle {pickle_path}")
                else:
                    print(f"Skipping loading from pickle as args differ given:{kwargs} loaded:{saved_kwargs}")

        if result is None:
            result = AnalysisResults(self.analyse_path(path, **kwargs))

            with open(pickle_path, 'wb') as pickle_file:
                pickle.dump(kwargs, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)
                pickle.dump(result, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

        return result

    def analyse_and_summarise_path_wrapped(self, path, flush, **kwargs):
        """Calls analyse_and_summarise_path, but wrapped inside a Process.
        This forces memory allocated during the analysis to be freed."""
        def wrapped(queue, path, flush, **kwargs):
            queue.put(self.analyse_and_summarise_path(path, flush, **kwargs))

            print("Memory usage of worker:", pprint_ntuple(psutil.Process().memory_full_info()))

        q = multiprocessing.Queue(1)
        p = multiprocessing.Process(target=wrapped, args=(q, path, flush), kwargs=kwargs)
        p.start()
        result = q.get()
        p.join()

        return result

    def run(self, summary_file, result_finder, nprocs=None, testbed=False, flush=False, **kwargs):
        """Perform the analysis and write the output to the :summary_file:.
        If :nprocs: is not specified then the number of CPU cores will be used.
        """

        if testbed:
            # Do not attempt to verify that same seed runs have the same results.
            # The testbed are not deterministic like that!
            kwargs["verify_seeds"] = False

            # Need to remove parameters that testbed runs do not have
            #for name in simulator.common.testbed_missing_global_parameter_names:
            #    del self.values[name]

        # Skip the overhead of the queue with 1 process.
        # This also allows easy profiling
        if nprocs is not None and nprocs == 1:
            return self.run_single(summary_file, result_finder, flush, **kwargs)

        def worker(inqueue, outqueue):
            while True:
                item = inqueue.get()

                if item is None:
                    return

                path = item

                try:
                    result = self.analyse_and_summarise_path(path, flush, **kwargs)

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

            print(f"Using {nprocs} threads")

        inqueue = multiprocessing.Queue()
        outqueue = multiprocessing.Queue()

        pool = multiprocessing.Pool(nprocs, worker, (inqueue, outqueue))

        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process.
        # These are sorted to give anyone watching the output a sense of progress.
        files = sorted(result_finder(self.results_directory))

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

                print(f'Analysing {path}')

                if error is None:
                    print(line, file=out)
                else:
                    (ex, tb) = error
                    print(f"Error processing {path} with {ex}")
                    print(tb)

                progress.print_progress(num)

            print(f'Finished writing {summary_file_path}')

        inqueue.close()
        inqueue.join_thread()

        outqueue.close()
        outqueue.join_thread()

        pool.close()
        pool.join()

    def run_single(self, summary_file, result_finder, flush=False, **kwargs):
        """Perform the analysis and write the output to the :summary_file:"""
        
        def worker(ipath):
            result = self.analyse_and_summarise_path_wrapped(path, flush, **kwargs)

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
        files = sorted(result_finder(self.results_directory))

        with open(summary_file_path, 'w') as out:

            print("|".join(self.values.keys()), file=out)

            progress = Progress("analysing file")
            progress.start(len(files))

            for num, infile in enumerate(files):
                path = os.path.join(self.results_directory, infile)

                print(f'Analysing {path}')

                try:
                    line = worker(path)

                    print(line, file=out)
                except Exception as ex:
                    print(f"Error processing {path} with {ex}")
                    print(traceback.format_exc())

                progress.print_progress(num)

            print(f'Finished writing {summary_file}')
