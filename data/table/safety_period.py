# Author: Matthew Bradbury
import itertools
from functools import partial

from simulator.Configuration import configuration_rank

from data import latex, results

class TableGenerator:
    def __init__(self, sim_name, result_file, tafn_to_safety_period, fmt=None):
        self._sim_name = sim_name
        self._result_names = ('received ratio',
                              'normal latency', 'ssd', 'captured',
                              'time after first normal', 'repeats')

        self._results = results.Results(
            sim_name,
            result_file,
            parameters=tuple(),
            results=self._result_names
        )

        self.tafn_to_safety_period = tafn_to_safety_period

        self.fmt = fmt
        if fmt is None:
            from data.table.data_formatter import TableDataFormatter
            self.fmt = TableDataFormatter()

    def _get_name_and_value(self, result, name):
        return name, result[self._result_names.index(name)]

    def _get_just_value(self, result, name):
        return result[self._result_names.index(name)]['mean']

    def write_tables(self, *args, **kwargs):
        if self._sim_name == "real":
            self._write_testbed_tables(*args, **kwargs)
        else:
            self._write_tables(*args, **kwargs)

    def _write_tables(self, stream, param_filter=None):

        global_parameter_names = self._results.global_parameter_names

        global_values = [
            tuple(sorted(getattr(self._results, self._results.name_to_attr(name))))
            for name
            in global_parameter_names
        ]

        product_all = list(itertools.product(*global_values))

        all_keys = set(self._results.data.keys())

        network_size_index = global_parameter_names.index('network size')

        # Get rid of network size
        filtered_product = [x[:network_size_index] + x[network_size_index+1:] for x in product_all if x in all_keys]
        global_parameter_names = global_parameter_names[:network_size_index] + global_parameter_names[network_size_index+1:]

        network_sizes = {x[network_size_index] for x in product_all}

        if not any(table_key in self._results.data for table_key in product_all):
            raise RuntimeError("Could not find any parameter combination in the results")

        # Convert to set to remove duplicates
        for product_key in sorted(set(filtered_product)):

            product_key_dict = dict(zip(global_parameter_names, product_key))

            print(product_key_dict)

            if param_filter is not None and not param_filter(product_key_dict):
                print("Skipping {}".format(product_key))
                continue

            caption_string = " and ".join(
                f"\\textbf{{{latex.escape(product_key[i])}}} {name}"
                for (i, name) in enumerate(global_parameter_names)
            )

            print('\\begin{table}[H]', file=stream)
            print('\\vspace{-0.35cm}', file=stream)
            print('\\caption{{Safety Periods for the {}}}'.format(caption_string), file=stream)
            print('\\centering', file=stream)
            print('\\begin{tabular}{ | c | c || c | c | c | c | c || c || c | }', file=stream)
            print('\\hline', file=stream)
            print('Size & Period & Received & Source-Sink   & Latency   & Repeats & Time After First  & Safety Period & Captured \\tabularnewline', file=stream)
            print('~    & (sec)  & (\\%)    & Distance (hop)& (msec)    & ~       & Normal (seconds)  & (seconds)     & (\\%)    \\tabularnewline', file=stream)
            print('\\hline', file=stream)
            print('', file=stream)

            for size in sorted(network_sizes, key=int):

                data_key = product_key[:network_size_index] + (size,) + product_key[network_size_index:]

                if data_key not in self._results.data:
                    print("Skipping {} as it could not be found in the results".format(data_key))
                    continue

                for src_period in sorted(self._results.data[data_key]):

                    result = self._results.data[data_key][src_period][tuple()]

                    get_name_and_value = partial(self._get_name_and_value, result)
                    get_just_value = partial(self._get_just_value, result)

                    safety_period = self.tafn_to_safety_period(
                        get_just_value('time after first normal'))

                    rcvd_ratio = self.fmt.format_value(*get_name_and_value('received ratio'))
                    ssd = self.fmt.format_value(*get_name_and_value('ssd'))
                    lat = self.fmt.format_value(*get_name_and_value('normal latency'))
                    tafn = self.fmt.format_value(*get_name_and_value('time after first normal'))
                    cap = self.fmt.format_value(*get_name_and_value('captured'))
                    repeats = self.fmt.format_value(*get_name_and_value('repeats'))
                
                    print(f'{size} & {src_period} & {rcvd_ratio} & {ssd} & {lat} & {repeats} & {tafn} & {safety_period:0.2f} & {cap} \\tabularnewline', file=stream)
                    
                print('\\hline', file=stream)
                print('', file=stream)

            print('\\end{tabular}', file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)

    def _write_testbed_tables(self, stream, param_filter=lambda *args: True):

        global_parameter_names = self._results.global_parameter_names

        global_values = [
            tuple(sorted(getattr(self._results, self._results.name_to_attr(name))))
            for name
            in global_parameter_names
        ]

        product_all = list(itertools.product(*global_values))

        all_keys = set(self._results.data.keys())

        if not any(table_key in self._results.data for table_key in product_all):
            raise RuntimeError("Could not find any parameter combination in the results")

        for product_key in sorted(product_all):
            product_key_dict = dict(zip(global_parameter_names, product_key))

            print(product_key_dict)

            if param_filter is not None and not param_filter(product_key_dict):
                print("Skipping {}".format(product_key))
                continue

            caption_string = " and ".join(
                f"\\textbf{{{latex.escape(product_key[i])}}} {name}"
                for (i, name) in enumerate(global_parameter_names)
            )

            print('\\begin{table}[H]', file=stream)
            print('\\vspace{-0.35cm}', file=stream)
            print('\\caption{{Safety Periods for the {}}}'.format(caption_string), file=stream)
            print('\\centering', file=stream)
            print('\\begin{tabular}{ | c || c | c | c | c | c || c || c | }', file=stream)
            print('\\hline', file=stream)
            print('Period & Received & Source-Sink   & Latency   & Repeats & Time After First  & Safety Period & Captured \\tabularnewline', file=stream)
            print('(sec)  & (\\%)    & Distance (hop)& (msec)    & ~       & Normal (seconds)  & (seconds)     & (\\%)    \\tabularnewline', file=stream)
            print('\\hline', file=stream)
            print('', file=stream)

            if product_key not in self._results.data:
                print("Skipping {} as it could not be found in the results".format(data_key))
                continue

            for src_period in sorted(self._results.data[product_key]):

                result = self._results.data[product_key][src_period][tuple()]

                get_name_and_value = partial(self._get_name_and_value, result)
                get_just_value = partial(self._get_just_value, result)

                safety_period = self.tafn_to_safety_period(
                    get_just_value('time after first normal'))

                rcvd_ratio = self.fmt.format_value(*get_name_and_value('received ratio'))
                ssd = self.fmt.format_value(*get_name_and_value('ssd'))
                lat = self.fmt.format_value(*get_name_and_value('normal latency'))
                tafn = self.fmt.format_value(*get_name_and_value('time after first normal'))
                cap = self.fmt.format_value(*get_name_and_value('captured'))
                repeats = self.fmt.format_value(*get_name_and_value('repeats'))
            
                print(f'{src_period} & {rcvd_ratio} & {ssd} & {lat} & {repeats} & {tafn} & {safety_period:0.2f} & {cap} \\tabularnewline', file=stream)

            print('\\hline', file=stream)
            print('\\end{tabular}', file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)

    def _get_result_mapping(self, result_names, accessor):
        # (size, configuration, attacker model, noise model, communication model, fault model, distance) -> source period -> individual result
        result = {}

        try:
            indexes = [self._result_names.index(result_name) for result_name in result_names]
        except ValueError as ex:
            raise RuntimeError(f"The results do not contain any of '{result_names}'. The available names are: '{self._result_names}'", ex)

        for (table_key, other_items) in self._results.data.items():
            for (source_period, items) in other_items.items():

                individual_results = [items[tuple()][index] for index in indexes]

                result.setdefault(table_key, {})[source_period] = accessor(*individual_results)

        return result

    def safety_periods(self):
        # (size, configuration, attacker model, noise model, communication model, distance) -> source period -> safety period
        return self._get_result_mapping(('time after first normal',),
                                        lambda tafn: self.tafn_to_safety_period(tafn['mean']))

    def time_taken(self):
        # (size, configuration, attacker model, noise model, communication model, distance) -> source period -> time taken
        return self._get_result_mapping(('time taken',),
                                        lambda tt: tt['mean'])
