from __future__ import print_function

import os

import data.util
from data import latex
from data.graph.grapher import GrapherBase

class Grapher(GrapherBase):
    def __init__(self, output_directory, results, result_name, shows, extractor=None, normalisor=None):
        super(Grapher, self).__init__(output_directory)

        self.results = results
        self.result_name = result_name

        self.shows = shows
        self.extractor = extractor if extractor is not None else lambda x: x
        self.normalisor = normalisor if normalisor is not None else lambda (kn, kv, p, v): v

        self.xaxis_label = 'Parameters'
        self.yaxis_label = None

    def create(self):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        dat = {}

        for ((size, config), items1) in self.results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = ('size', 'configuration', 'source period')
                    key_values = (size, config, src_period)

                    yvalues = []

                    for show in self.shows:
                        extracted = self.extractor(results[ self.results.result_names.index(show) ])
                        normalised = self.normalisor(key_names, key_values, params, extracted)
                        yvalues.append(normalised)

                    dat.setdefault((key_names, key_values), {})[params] = yvalues

        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)

    def _create_plot(self, key_names, key_values, values):
        dir_name = os.path.join(self.output_directory, self.result_name, *map(str, key_values))

        print(dir_name)

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        all_positive = True

        def quote(s):
            return "\"{}\"".format(s)

        # Write our data
        with open(os.path.join(dir_name, 'graph.dat'), 'w') as graph_dat:

            xvalues = list(sorted({x for x in values.keys()}))

            table =  [ [ '#' ] + list(map(quote, self.shows)) ]

            for xvalue in xvalues:
                barvalues = values.get(xvalue, '?')
                row = [ quote(xvalue) ] + barvalues

                for value in barvalues:
                    all_positive &= value >= 0

                table.append(row)

            self._pprint_table(graph_dat, table)


        with open(os.path.join(dir_name, 'graph.p'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')

            if self.xaxis_label is not None:
                graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))

            if self.yaxis_label is not None:
                graph_p.write('set ylabel "{}"\n'.format(self.yaxis_label))

            graph_p.write('set style data histogram\n')
            graph_p.write('set style histogram cluster gap 1\n')
            graph_p.write('set style fill solid border -1\n')

            graph_p.write('set xtic rotate by -90 scale 0\n')

            graph_p.write('set xtics font ",8"\n')

            graph_p.write('set key right top\n')

            # When all data is positive, make sure to include
            # 0 on the y axis.
            if all_positive:
                graph_p.write('set yrange [0:]\n')
            
            graph_p.write('set output "graph.pdf"\n')
            
            plots = []

            for i, show in enumerate(self.shows):
                if i == 0:
                    plots.append('"graph.dat" using {}:xticlabels(1) ti "{}"'.format(i + 2, show))
                else:
                    plots.append('"graph.dat" using {} ti "{}"'.format(i + 2, show))

            graph_p.write('plot {}\n\n'.format(', '.join(plots)))
        

        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Parameters:\\newline\n')
            for (name, value) in zip(key_names, key_values):
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))

class DiffGrapher(Grapher):
    def create(self):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        dat = {}

        for ((size, config), items1) in self.results.diff.items():
            for (comp_params, items2) in items1.items():
                for (src_period, items3) in items2.items():
                    for (params, results) in items3.items():

                        key_names = tuple(['size', 'configuration', 'source period'] + self.results.comparison_results.parameter_names)
                        key_values = tuple([size, config, src_period] + list(comp_params))

                        yvalues = []

                        for show in self.shows:
                            extracted = self.extractor(results[ self.results.comparison_results.result_names.index(show) ])
                            normalised = self.normalisor(key_names, key_values, params, extracted)
                            yvalues.append(normalised)

                        dat.setdefault((key_names, key_values), {})[params] = yvalues

        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)
