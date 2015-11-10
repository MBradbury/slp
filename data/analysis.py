from __future__ import print_function, division

from numpy import mean
from numpy import var as variance

import sys, ast, math, os, fnmatch, timeit, datetime, collections
from collections import Counter
from numbers import Number

class EmptyFileError(RuntimeError):
    def __init__(self, filename):
        super(EmptyFileError, self).__init__("The file '{}' is empty.".format(filename))


def _normalised_value_name(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, collections.Sequence) and len(value) == 2:
        return "norm({},{})".format(_normalised_value_name(value[0]), _normalised_value_name(value[1]))
    else:
        raise RuntimeError("Unknown type or length for value {}".format(value))

def _normalised_value_names(values):
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
            raise RuntimeError("Unknown type or length for value {}".format(value))

        return result

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
    def __init__(self, infile, normalised_values):

        self.opts = {}

        self.headings = []
        self.data = []

        self._unnormalised_headings_count = None

        with open(infile) as f:
            line_number = 0

            for line in f:

                line_number += 1

                # We need to remove the new line at the end of the line
                line = line.strip()

                if '=' in line and len(self.headings) == 0:
                    # We are reading the options so record them
                    opt = line.split('=')

                    # Need to handle values that have an "=" in them
                    self.opts[opt[0]] = '='.join(opt[1:])

                elif line.startswith('#'):
                    # Read the headings
                    self.headings = line[1:].split('|')

                    self._unnormalised_headings_count = len(self.headings)

                    self.headings.extend(_normalised_value_names(normalised_values))

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

                        self.data.append(values)


                    except (TypeError, RuntimeError) as e:
                        print("Unable to process line {} due to {}".format(line_number, e), file=sys.stderr)

                else:
                    print("Unable to parse line {} : '{}'".format(line_number, line))

            if line_number == 0 or len(self.data) == 0:
                raise EmptyFileError(infile)

    def _get_from_opts_or_values(self, name, values):
        try:
            index = self.headings.index(_normalised_value_name(name))

            return values[index]
        except ValueError:
            # Sorry for this horrible hack, but we really should
            # have stored network size as its actual value from the start
            if name == "network_size":
                return float(self.opts[name]) ** 2
            elif name == "source_rate":
                return 1.0 / float(self.opts["source_period"])
            else:
                return float(self.opts[name])


    def _better_literal_eval(self, line_number, items):
        values = []

        for (heading, item) in zip(self.headings, items):

            # ast.literal_eval will not parse inf correctly.
            # passing 2e308 will return a float('inf') instead.
            item = item.replace('inf', '2e308')

            try:
                lit = ast.literal_eval(item)
            except ValueError as e:
                print("Unable to process line {} due to {} ({}={})".format(line_number, e, heading, item), file=sys.stderr)
                lit = None

            values.append(lit)

        return values


    def check_consistent(self, values, line_number):
        """Perform multiple sanity checks on the data generated"""

        # Check that the expected number of values are present
        if len(values) != self._unnormalised_headings_count:
            raise RuntimeError("The number of values {} doesn't equal the number of headings {} on line {}".format(
                len(values), len(self.headings), line_number))

        network_size = int(self.opts['network_size'])
        number_nodes = network_size * network_size

        for (heading, value) in zip(self.headings, values):
            if type(value) is dict and heading in {'SentHeatMap', 'ReceivedHeatMap'}:

                # Check that there aren't too many nodes
                if len(value) > number_nodes:
                    raise RuntimeError("There are too many nodes in this map {} called {}, when there should be {} maximum.".format(len(value), heading, number_nodes))

                # Check that the node ids are in the right range
                #for k in value.keys():
                #    if k < 0 or k >= number_nodes:
                #        raise RuntimeError("The key {} is invalid for this map it is not between {} and {}".format(k, 0, number_nodes))

        self._check_captured_consistent(values, line_number)

        # Check NormalLatency is not 0
        latency_index = self.headings.index("NormalLatency")
        latency = values[latency_index]

        if math.isnan(latency):
            raise RuntimeError('The NormalLatency {} is a NaN'.format(latency))

        if latency <= 0:
            raise RuntimeError("The NormalLatency {} is less than or equal to 0.".format(latency))
    
    def _check_captured_consistent(self, values, line_number):
        # If captured is set to true, there should be an attacker at the source location
        captured_index = self.headings.index("Captured")
        captured = values[captured_index]

        attacker_distance_index = self.headings.index("AttackerDistance")
        attacker_distance = values[attacker_distance_index]

        def is_close(x, y, rtol=1.e-5, atol=1.e-8):
            return abs(x-y) <= atol + rtol * abs(y)

        # Handle two sorts of attacker distance dicts
        # 1. {attacker_id: distance}
        # 2. {(source_id, attacker_id): distance}}
        any_at_source = any(
            is_close(dist, 0.0) if isinstance(dist, Number) else any(is_close(v, 0.0) for (k, v) in dist.items())
            for (attacker, dist)
            in attacker_distance.items()
        )

        if captured != any_at_source:
            raise RuntimeError("There is a discrepancy between captured ({}) and the attacker distances {}.".format(captured, attacker_distance))


    def detect_outlier(self, values):
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
        # Find the index that header refers to
        index = self.headings.index(header)

        if isinstance(self.data[0][index], dict):
            return self.dict_mean(index)
        else:
            # Some values may be inf, if they are lets ignore
            # the values that were inf.
            values = [self._to_float(values[index]) for values in self.data]
            filtered = [x for x in values if not math.isinf(x)]

            # Unless all the values are inf, when we should probably pass this
            # fact onwards.
            if len(filtered) != 0:
                return mean(filtered)
            else:
                return float('inf')

    def variance_of(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        if isinstance(self.data[0][index], dict):
            raise NotImplementedError()
        else:
            # Some values may be inf, if they are lets ignore
            # the values that were inf.
            values = [self._to_float(values[index]) for values in self.data]
            filtered = [x for x in values if not math.isinf(x)]

            # Unless all the values are inf, when we should probably pass this
            # fact onwards.
            if len(filtered) != 0:
                return variance(filtered)
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


    def dict_mean(self, index):

        dict_list = (values[index] for values in self.data)

        result = {
            k: float(v) / len(self.data)
            for (k, v)
            in self.dict_sum(dict_list).items()
        }

        return result


class AnalysisResults:
    def __init__(self, analysis):
        self.average_of = {}
        self.variance_of = {}
        
        for heading in analysis.headings:
            try:
                self.average_of[heading] = analysis.average_of(heading)
            except (TypeError, RuntimeError) as ex:
                print("Failed to average {}: {}".format(heading, ex), file=sys.stderr)
                #print(traceback.format_exc(), file=sys.stderr)
            
            try:
                self.variance_of[heading] = analysis.variance_of(heading)
            except (TypeError, RuntimeError) as ex:
                print("Failed to find variance {}: {}".format(heading, ex), file=sys.stderr)
                #print(traceback.format_exc(), file=sys.stderr)

        self.opts = analysis.opts
        self.data = analysis.data

class AnalyzerCommon(object):
    def __init__(self, results_directory, values, normalised_values=tuple()):
        self.results_directory = results_directory
        self.values = values
        self.normalised_values = normalised_values

    @staticmethod
    def _set_results_header(d):
        d['network size']       = lambda x: x.opts['network_size']
        d['configuration']      = lambda x: x.opts['configuration']
        d['attacker model']     = lambda x: x.opts['attacker_model']
        d['noise model']        = lambda x: x.opts['noise_model']
        d['communication model']= lambda x: x.opts['communication_model']
        d['source period']      = lambda x: x.opts['source_period']

    @staticmethod
    def _format_results(x, name, allow_missing=False, average_corrector=lambda x: x, variance_corrector=lambda x: x):
        if name in x.variance_of:
            average = average_corrector(x.average_of[name])
            variance = variance_corrector(x.variance_of[name])
            return "{}({})".format(average, variance)
        else:
            try:
                average = average_corrector(x.average_of[name])
                return "{}".format(average)
            except KeyError:
                if not allow_missing:
                    raise
                else:
                    return "None"

    def analyse_path(self, path):
        return AnalysisResults(Analyse(path, self.normalised_values))

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
                    result = self.analyse_path(path)
                    
                    # Skip 0 length results
                    if len(result.data) == 0:
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

            print('Finished writing {}'.format(summary_file))
