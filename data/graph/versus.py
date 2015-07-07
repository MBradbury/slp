from __future__ import print_function

import os

import data.util
from data import latex
from data.graph.grapher import GrapherBase

class Grapher(GrapherBase):

    _key_names_base = ['size', 'configuration', 'attacker model', 'noise model', 'communication model', 'source period']

    def __init__(self, output_directory, result_name,
                 xaxis, yaxis, vary, yextractor=lambda x: x):

        super(Grapher, self).__init__(output_directory)

        self.result_name = result_name

        self.xaxis = xaxis
        self.yaxis = yaxis
        self.vary = vary

        self.xaxis_label = xaxis
        self.yaxis_label = yaxis
        self.vary_label =  vary
        self.vary_prefix = ''

        self.yaxis_range_max = '*'

        self.yaxis_font = None
        self.xaxis_font = None

        self.key_position = 'right top'
        self.key_font = None
        self.key_spacing = None
        self.key_width = None
        self.key_height = None

        self.pointsize = '1'

        self.yextractor = yextractor

    @staticmethod        
    def _remove_index(names, values, index_name):
        idx = names.index(index_name)

        value = values[idx]

        del names[idx]
        del values[idx]

        return (names, values, value)

    def create(self, simulation_results):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        dat = {}

        for (data_key, items1) in simulation_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = self._key_names_base + simulation_results.parameter_names

                    values = list(data_key) + [src_period] + list(params)

                    (key_names, values, xvalue) = self._remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = self._remove_index(key_names, values, self.vary)

                    key_names = tuple(key_names)
                    values = tuple(values)

                    yvalue = results[ simulation_results.result_names.index(self.yaxis) ]

                    dat.setdefault((key_names, values), {})[(xvalue, vvalue)] = self.yextractor(yvalue)

        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)

    def _create_plot(self, key_names, key_values, values):
        dir_name = os.path.join(self.output_directory, self.result_name, *map(str, key_values))

        print("Currently in " + dir_name)

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        # Write our data
        with open(os.path.join(dir_name, 'graph.dat'), 'w') as graph_dat:

            xvalues = list({x[0] for x in values.keys()})
            vvalues = list(sorted({x[1] for x in values.keys()}))

            table =  [ [ '#' ] + vvalues ]

            for xvalue in sorted(xvalues):
                row = [ xvalue ]
                for vvalue in vvalues:
                    row.append(values.get((xvalue, vvalue), '?'))

                table.append(row)

            self._pprint_table(graph_dat, table)

        columnCount = len(vvalues)


        with open(os.path.join(dir_name, 'graph.gp'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')

            graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))
            graph_p.write('set ylabel "{}"\n'.format(self.yaxis_label))
            graph_p.write('set pointsize {}\n'.format(self.pointsize))
            graph_p.write('set key {}\n'.format(self.key_position))

            if self.key_font is not None:
                graph_p.write('set key font {}\n'.format(self.key_font))

            if self.key_spacing is not None:
                graph_p.write('set key spacing {}\n'.format(self.key_spacing))

            if self.key_width is not None:
                graph_p.write('set key width {}\n'.format(self.key_width))

            if self.key_height is not None:
                graph_p.write('set key height {}\n'.format(self.key_height))

            # Should remain the same as we are testing with
            # a limited sized grid of nodes
            graph_p.write('set xrange [{}:{}]\n'.format(min(xvalues) - 1, max(xvalues) + 1))
            graph_p.write('set xtics ({})\n'.format(",".join(map(str, xvalues))))

            if self.xaxis_font is not None:
                graph_p.write('set xtics font {}\n'.format(self.xaxis_font))

            graph_p.write('set yrange [0:{}]\n'.format(self.yaxis_range_max))
            graph_p.write('set ytics auto\n')

            if self.yaxis_font is not None:
                graph_p.write('set ytics font {}\n'.format(self.yaxis_font))
            
            graph_p.write('set output "graph.pdf"\n')
            
            plots = []

            for x in range(1, columnCount + 1):
                plots.append('"graph.dat" u 1:{} w lp ti \'{} {}{}\''.format(
                    x + 1, self.vary_label, vvalues[ x - 1 ], self.vary_prefix))

            graph_p.write('plot {}\n\n'.format(', '.join(plots)))
        

        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Parameters:\\newline\n')
            for (name, value) in zip(key_names, key_values):
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))
