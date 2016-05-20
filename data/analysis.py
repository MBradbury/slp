from __future__ import print_function, division

import numpy
from numpy import mean, median
from numpy import var as variance

import sys, ast, math, os, fnmatch, timeit, datetime, collections, traceback
from collections import OrderedDict
from numbers import Number

import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel

class EmptyFileError(RuntimeError):
    def __init__(self, filename):
        super(EmptyFileError, self).__init__("The file '{}' is empty.".format(filename))


def _normalised_value_name(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, collections.Sequence) and len(value) == 2:
        return "norm({},{})".format(_normalised_value_name(value[0]), _normalised_value_name(value[1]))
    else:
        raise RuntimeError("Unknown type or length for value '{}' of type {}".format(value, type(value)))

def _dfs_names(value):
    result = []

    if isinstance(value, str):
        #result.append(value)
        pass
    elif isinstance(value, collections.Sequence) and len(value) == 2:
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

    # Get unique results maintaining insertion order
    result = []
    for r in all_results:
        if r not in result:
            result.append(r)

    return result

class Analyse(object):

    # When a converter is not present, the custom literal eval will be used
    FAST_HEADINGS_CONVERTERS = {
        "Seed": int,
        "Sent": int,
        "Captured": lambda x: x == "True",
        "Received": int,
        "ReceiveRatio": float,
        "TimeTaken": float,
        "WallTime": float,
        "EventCount": int,
        "NormalLatency": float,
        "NormalSinkSourceHops": float,
        "NormalSent": int,
        "SentHeatMap": ast.literal_eval,
        "ReceivedHeatMap": ast.literal_eval,
        "AttackerDistance": ast.literal_eval,
        "AttackerMoves": ast.literal_eval,
        #"NodeWasSource": ast.literal_eval, # Doesn't work due to inf strings
    }

    def __init__(self, infile, normalised_values):

        self.opts = {}

        self.headings = []
        #self.data = []
        self.columns = {}

        self._unnormalised_headings_count = None

        with open(infile, 'r') as f:
            line_number = 0

            for line in f:

                line_number += 1

                # We need to remove the new line at the end of the line
                line = line.strip()

                if len(self.headings) == 0 and '=' in line:
                    # We are reading the options so record them.
                    # Some option values will have an '=' in them so only split once.
                    opt = line.split('=', 1)

                    self.opts[opt[0]] = opt[1]

                elif line.startswith('#'):
                    # Read the headings
                    self.headings = line[1:].split('|')

                    self._unnormalised_headings_count = len(self.headings)

                    self.headings.extend(_normalised_value_names(normalised_values))

                    self.columns = {heading: list() for heading in self.headings}

                elif '|' in line:
                    try:
                        # Read the actual data
                        values = self._better_literal_eval(line_number, line.split('|'))

                        self.check_consistent(values, line_number)

                        self.detect_outlier(values)

                        # Create the per line normalised values
                        for (num, den) in normalised_values:
                            num_value = self._get_from_opts_or_values(_normalised_value_name(num), values)
                            den_value = self._get_from_opts_or_values(_normalised_value_name(den), values)

                            values.append(num_value / den_value)

                        #self.data.append(values)

                        for (name, value) in zip(self.headings, values):
                            self.columns[name].append(value)

                    except (TypeError, RuntimeError, SyntaxError) as e:
                        print("Unable to process line {} due to {}".format(line_number, e), file=sys.stderr)

                else:
                    print("Unable to parse line {} : '{}'".format(line_number, line))

            if line_number == 0 or len(next(iter(self.columns))) == 0:
                raise EmptyFileError(infile)

    def _get_configuration(self):
        return Configuration.create_specific(self.opts['configuration'],
                                             int(self.opts['network_size']),
                                             float(self.opts['distance']))

    def _get_from_opts_or_values(self, name, values):
        try:
            index = self.headings.index(_normalised_value_name(name))

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

                return (energy_impact_per_node_per_day / daily_allowance_mah) * 100.0

            elif name == "1":
                return 1.0

            else:
                return float(self.opts[name])


    def _better_literal_eval(self, line_number, items):
        
        if self._unnormalised_headings_count != len(items):
            raise RuntimeError("The number of headings ({}) is not the same as the number of values ({}) on line {}".format(
                self._unnormalised_headings_count, len(items), line_number))

        values = []

        lit = None

        for (heading, item) in zip(self.headings, items):

            fast_eval = self.FAST_HEADINGS_CONVERTERS.get(heading, None)

            try:
                if fast_eval is not None:
                    lit = fast_eval(item)
                else:
                    # ast.literal_eval will not parse inf correctly.
                    # passing 2e308 will return a float('inf') instead.
                    #
                    # The fast_eval version will parse inf when on its own correctly,
                    # so this hack is not needed there.
                    item = item.replace('inf', '2e308')

                    lit = ast.literal_eval(item)
            except ValueError as e:
                print("Unable to process line {} due to {} ({}={})".format(line_number, e, heading, item), file=sys.stderr)
                lit = None

            values.append(lit)

        return values


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
            numpy.isclose(dist, 0.0) if isinstance(dist, Number) else any(numpy.isclose(v, 0.0) for (k, v) in dist.items())
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

    @staticmethod
    def _to_float(value):
        """Convert boolean to floats to allow averaging
        the number of time the source was captured."""
        if value is True:
            return 1.0
        elif value is False:
            return 0.0
        else:
            return float(value)

    def average_of(self, header):
        values = self.columns[header]

        if isinstance(values[0], dict):
            return self.dict_mean(values)
        else:
            # Some values may be inf, if they are lets ignore the values that were inf.
            filtered = [x for x in (self._to_float(value) for value in values) if not math.isinf(x)]

            # Unless all the values are inf, when we should probably pass this fact onwards.
            if len(filtered) != 0:
                return mean(filtered)
            else:
                return float('inf')

    def variance_of(self, header):
        values = self.columns[header]

        if isinstance(values[0], dict):
            raise NotImplementedError()
        else:
            # Some values may be inf, if they are lets ignore the values that were inf.
            filtered = [x for x in (self._to_float(value) for value in values) if not math.isinf(x)]

            # Unless all the values are inf, when we should probably pass this fact onwards.
            if len(filtered) != 0:
                return variance(filtered)
            else:
                return float('nan')

    def median_of(self, header):
        values = self.columns[header]

        if isinstance(values[0], dict):
            raise NotImplementedError()
        else:
            # Some values may be inf, if they are lets ignore the values that were inf.
            filtered = [x for x in (self._to_float(value) for value in values) if not math.isinf(x)]

            # Unless all the values are inf, when we should probably pass this fact onwards.
            if len(filtered) != 0:
                return median(values)
            else:
                return float('nan')


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

        expected_fail = ['Collisions']

        for heading in analysis.headings:
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

        self.median_of['TimeTaken'] = analysis.average_of('TimeTaken')

        self.opts = analysis.opts
        #self.data = analysis.data
        self.columns = analysis.columns

    def number_of_repeats(self):
        # Get a name of any of the columns
        aname = next(iter(self.columns))

        # Find the length of that list
        return len(self.columns[aname])

class AnalyzerCommon(object):
    def __init__(self, results_directory, values, normalised_values=tuple()):
        self.results_directory = results_directory
        self.values = values
        self.normalised_values = normalised_values

    @staticmethod
    def common_results_header():
        d = OrderedDict()
        
        # Include the number of simulations that were analysed
        d['repeats']            = lambda x: str(x.number_of_repeats())

        # The options that all simulations must include
        d['network size']       = lambda x: x.opts['network_size']
        d['configuration']      = lambda x: x.opts['configuration']
        d['attacker model']     = lambda x: x.opts['attacker_model']
        d['noise model']        = lambda x: x.opts['noise_model']
        d['communication model']= lambda x: x.opts['communication_model']
        d['distance']           = lambda x: x.opts['distance']
        d['source period']      = lambda x: x.opts['source_period']

        return d

    @staticmethod
    def common_results(d):
        # These metrics are ones that all simulations should have
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
        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process.
        # These are sorted to give anyone watching the output a sense of progress.
        files = sorted(fnmatch.filter(os.listdir(self.results_directory), '*.txt'))

        total = len(files)

        with open(summary_file_path, 'w') as out:

            print("|".join(self.values.keys()), file=out)

            start_time = timeit.default_timer()

            for (num, infile) in enumerate(files):
                path = os.path.join(self.results_directory, infile)

                print('Analysing {0}'.format(path))
            
                try:
                    result = self.analyse_and_summarise_path(path)
                    
                    # Skip 0 length results
                    if result.number_of_repeats() == 0:
                        print("Skipping as there is no data.")
                        continue

                    line_data = [fn(result) for fn in self.values.values()]

                    print("|".join(line_data), file=out)

                except EmptyFileError as e:
                    print(e)

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
