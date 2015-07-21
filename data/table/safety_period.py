# Author: Matthew Bradbury

from __future__ import print_function

import itertools

from simulator.Configuration import configuration_rank

from data import results

class TableGenerator:

    def __init__(self, result_file):
        self._result_names = ['time taken', 'received ratio', 'safety period', 'normal latency', 'ssd', 'captured']

        self._results = results.Results(
            result_file,
            parameters=tuple(),
            results=self._result_names
        )

    def write_tables(self, stream, param_filter=lambda x: True):

        communication_models = sorted(self._results.communication_models)
        noise_models = sorted(self._results.noise_models)
        attacker_models = sorted(self._results.attacker_models)
        configurations = sorted(self._results.configurations, key=configuration_rank)
        sizes = sorted(self._results.sizes)

        product_all = list(itertools.product(sizes, configurations, attacker_models, noise_models, communication_models))

        product_three = list(itertools.ifilter(
            lambda x: x in {(cm, n, a, c) for (s, c, a, n, cm) in self._results.data.keys()},
            itertools.product(communication_models, noise_models, attacker_models, configurations)
        ))

        for product_three_key in product_three:

            if not any(table_key in self._results.data for table_key in product_all):
                continue

            if not param_filter(product_three_key):
                continue

            (communication_model, noise_model, attacker_model, config) = product_three_key

            print('\\begin{table}', file=stream)
            print('\\vspace{-0.35cm}', file=stream)
            print('\\caption{{Safety Periods for the \\textbf{{{}}} configuration and \\textbf{{{}}} attacker model and \\textbf{{{}}} noise model and \\textbf{{{}}} communication model}}'.format(
                config, attacker_model, noise_model, communication_model), file=stream)
            print('\\centering', file=stream)
            print('\\begin{tabular}{ | c | c || c | c | c | c || c || c | }', file=stream)
            print('\\hline', file=stream)
            print('Size & Period & Received & Source-Sink   & Latency   & Average Time    & Safety Period & Captured \\tabularnewline', file=stream)
            print('~    & (sec)  & (\\%)    & Distance (hop)& (msec)    & Taken (seconds) & (seconds)     & (\\%)    \\tabularnewline', file=stream)
            print('\\hline', file=stream)
            print('', file=stream)

            for size in sorted(self._results.sizes):

                data_key = (size, config, attacker_model, noise_model, communication_model)

                if data_key not in self._results.data:
                    continue

                for src_period in sorted(self._results.data[data_key]):

                    result = self._results.data[data_key][src_period][tuple()]

                    def _get_value(name):
                        return result[self._result_names.index(name)]

                    rcv = _get_value('received ratio')
                    ssd = _get_value('ssd')
                    latency = _get_value('normal latency')
                    time_taken = _get_value('time taken')
                    safety_period = _get_value('safety period')
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

    def safety_periods(self):
        # (size, configuration, attacker model, noise model, communication model) -> source period -> safety period
        result = {}

        for (table_key, other_items) in self._results.data.items():
            for (source_period, items) in other_items.items():

                index = self._result_names.index('safety period')
                safety_period = items[tuple()][index]

                result.setdefault(table_key, {})[source_period] = safety_period

        return result
