# Author: Matthew Bradbury

from __future__ import print_function

import itertools

from simulator.Configuration import configuration_rank

from data import results

class TableGenerator:

    def __init__(self, result_file, time_taken_to_safety_period):
        self._result_names = ('time taken', 'received ratio',
                              'normal latency', 'ssd', 'captured',
                              'first normal sent time')

        self._results = results.Results(
            result_file,
            parameters=tuple(),
            results=self._result_names
        )

        self.time_taken_to_safety_period = time_taken_to_safety_period

    def write_tables(self, stream, param_filter=lambda x: True):

        communication_models = sorted(self._results.communication_models)
        noise_models = sorted(self._results.noise_models)
        attacker_models = sorted(self._results.attacker_models)
        configurations = sorted(self._results.configurations, key=configuration_rank)
        sizes = sorted(self._results.network_sizes)
        distances = sorted(self._results.distances)
        node_id_orders = sorted(self._results.node_id_orders)
        latest_start_times = sorted(self._results.latest_node_start_times)

        product_all = list(itertools.product(sizes, configurations, attacker_models, noise_models, communication_models, distances, node_id_orders, latest_start_times))

        product_three = list(itertools.ifilter(
            lambda x: x in {(cm, n, a, c, d, nido, lst) for (s, c, a, n, cm, d, nido, lst) in self._results.data.keys()},
            itertools.product(communication_models, noise_models, attacker_models, configurations, distances, node_id_orders, latest_start_times)
        ))

        if not any(table_key in self._results.data for table_key in product_all):
            raise RuntimeError("Could not find any parameter combination in the results")

        for product_three_key in product_three:
            if not param_filter(product_three_key):
                continue

            (communication_model, noise_model, attacker_model, config, distance, node_id_order, latest_start_time) = product_three_key

            print('\\begin{table}[H]', file=stream)
            print('\\vspace{-0.35cm}', file=stream)
            print('\\caption{{Safety Periods for the \\textbf{{{}}} configuration and \\textbf{{{}}} attacker model and \\textbf{{{}}} noise model and \\textbf{{{}}} communication model and \\textbf{{{}}} distance and \\textbf{{{}}} node id order and \\textbf{{{}}} latest start time}}'.format(
                config, attacker_model, noise_model, communication_model, distance, node_id_order, latest_start_time), file=stream)
            print('\\centering', file=stream)
            print('\\begin{tabular}{ | c | c || c | c | c | c || c || c | }', file=stream)
            print('\\hline', file=stream)
            print('Size & Period & Received & Source-Sink   & Latency   & Average Time    & Safety Period & Captured \\tabularnewline', file=stream)
            print('~    & (sec)  & (\\%)    & Distance (hop)& (msec)    & Taken (seconds) & (seconds)     & (\\%)    \\tabularnewline', file=stream)
            print('\\hline', file=stream)
            print('', file=stream)

            for size in sizes:

                data_key = (size, config, attacker_model, noise_model, communication_model, distance, node_id_order, latest_start_time)

                if data_key not in self._results.data:
                    #print("Skipping {} as it could not be found in the results".format(data_key))
                    continue

                for src_period in sorted(self._results.data[data_key]):

                    result = self._results.data[data_key][src_period][tuple()]

                    def _get_value(name):
                        return result[self._result_names.index(name)]

                    rcv = _get_value('received ratio')
                    ssd = _get_value('ssd')
                    latency = _get_value('normal latency')
                    time_taken = _get_value('time taken')
                    first_normal_sent_time = _get_value('first normal sent time')
                    safety_period = self.time_taken_to_safety_period(time_taken[0], first_normal_sent_time[0])
                    captured = _get_value('captured')
                
                    print('{} & {} & {:0.0f} $\\pm$ {:0.2f} & {:.1f} $\\pm$ {:.2f}'
                          ' & {:0.1f} $\\pm$ {:0.1f} & {:0.2f} $\\pm$ {:0.2f}'
                          ' & {:0.2f} & {:0.0f} \\tabularnewline'.format(
                            size,
                            src_period,
                            rcv[0], rcv[1],
                            ssd[0], ssd[1],
                            latency[0], latency[1],
                            time_taken[0], time_taken[1],
                            safety_period,
                            captured),
                          file=stream)
                    
                print('\\hline', file=stream)
                print('', file=stream)

            print('\\end{tabular}', file=stream)
            print('\\label{{tab:safety-periods-{}}}'.format(config), file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)


    def _get_result_mapping(self, result_names, accessor):
        # (size, configuration, attacker model, noise model, communication model, distance) -> source period -> individual result
        result = {}

        indexes = [self._result_names.index(result_name) for result_name in result_names]

        for (table_key, other_items) in self._results.data.items():
            for (source_period, items) in other_items.items():

                individual_results = [items[tuple()][index] for index in indexes]

                result.setdefault(table_key, {})[source_period] = accessor(*individual_results)

        return result

    def safety_periods(self):
        # (size, configuration, attacker model, noise model, communication model, distance) -> source period -> safety period
        return self._get_result_mapping(('time taken', 'first normal sent time'),
                                        lambda tt, fnst: self.time_taken_to_safety_period(tt[0], fnst[0]))

    def time_taken(self):
        # (size, configuration, attacker model, noise model, communication model, distance) -> source period -> time taken
        return self._get_result_mapping(('time taken',),
                                        lambda tt: tt[0])
