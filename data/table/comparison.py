from __future__ import print_function

import csv
import numpy

from simulator.Configuration import configurationRank

class ResultTable:
    bad = '\\badcolour'
    good = '\\goodcolour'
    neutral = ''

    def _configuration_rank(self, configuration):
        return configurationRank[configuration] if configuration in configurationRank else len(rank) + 1

    class ResultsReader:
        def __init__(self, path):
            def read(value):
                if '(' in value:
                    return float(value.split('(')[0])
                else:
                    return float(value)

            headers = []
            self.data = {}

            self.sizes = set()
            self.configs = set()
            self.periods = set()

            with open(path, 'r') as f:
                reader = csv.reader(f, delimiter=',')
                for values in reader:
                    if len(headers) == 0:
                        headers = values
                    else:
                        size = int(values[ headers.index('network size') ])
                        config = values[ headers.index('configuration') ]

                        if 'source period' in headers:
                            srcPeriod = float(values[ headers.index('source period') ])
                        else:
                            srcPeriod = float(values[ headers.index('source rate') ])

                        self.sizes.add(size)
                        self.configs.add(config)
                        self.periods.add(srcPeriod)

                        sent = read(values[ headers.index('Sent') ])
                        received = read(values[ headers.index('Received') ])
                        collisions = read(values[ headers.index('Collisions') ])
                        captured = read(values[ headers.index('Captured') ]) * 100.0
                        received_ratio = read(values[ headers.index('Received Ratio') ]) * 100.0
                        time = read(values[ headers.index('Time') ])
                        normal = read(values[ headers.index('Normal') ])
                        away = read(values[ headers.index('Away') ])
                        choose = read(values[ headers.index('Choose') ])
                        fake = read(values[ headers.index('Fake') ])
                        TFS = read(values[ headers.index('TFS') ])
                        PFS = read(values[ headers.index('PFS') ])

                        self.data[ (config, size, srcPeriod) ] = \
                            (sent, received, collisions, captured,
                            received_ratio, time, normal, away, choose,
                            fake, TFS, PFS)


    def __init__(self, base_results_path, comparison_path):
        self.base = self.ResultsReader(base_results_path)
        self.comp = self.ResultsReader(comparison_path)

        self.create_diff()

    def create_diff(self):
        self.diff = {}

        for config in self.base.configs:
            for size in self.base.sizes:
                for period in self.base.periods:
                    key = (config, size, period)

                    base = self.base.data[key]
                    comp = self.comp.data[key]

                    diff = tuple(numpy.subtract(base, comp))

                    self.diff[key] = diff

    def colour_neg(self, value):
        if value < 0:
            return self.good
        else:
            return self.bad

    def colour_pos(self, value):
        if value > 0:
            return self.good
        else:
            return self.bad

    def write_tables(self, stream):
        for config in sorted(self.base.configs, key=self._configuration_rank):
            print('\\begin{table}[H]', file=stream)
            print('    \\centering', file=stream)
            print('    \\begin{tabular}{|l|l||l|l|l|l|}', file=stream)
            print('        \\hline', file=stream)
            print('        Size & Source Period & Captured & Normal   & Fake     & Received \\\\', file=stream)
            print('        ~    & (seconds)     & (\\%)    & Messages & Messages & (\\%)    \\\\', file=stream)
            print('        \\hline', file=stream)

            for size in sorted(self.base.sizes):
                print('        \\multirow{{4}}{{*}}{{{0}}}'.format(size), file=stream)

                for period in sorted(self.base.periods):

                    (sent, received, collisions, captured,
                            received_ratio, time, normal, away, choose,
                            fake, TFS, PFS) = self.diff[ (config, size, period) ]

                    print('        ~ & {} & {} {:+.2f} & {} {:+.0f} & {} {:+.0f} & {} {:+.2f} \\\\'.format(
                        float(period),
                        self.colour_neg(captured), captured,
                        self.colour_pos(normal), normal,
                        self.colour_neg(fake), fake,
                        self.colour_pos(received_ratio), received_ratio
                        ), file=stream)

                print('        \\hline', file=stream)
                print('', file=stream)

            print('    \\end{tabular}', file=stream)
            print('\\caption{{Adaptive results for the {0} configuration}}'.format(config), file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)

