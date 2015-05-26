from __future__ import print_function

import os

import data.util
from data import latex
from data.graph.grapher import GrapherBase

class Grapher(GrapherBase):
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

        self.key_position = 'right top'

        self.yextractor = yextractor

    @staticmethod        
    def remove_index(names, values, index_name):
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

        for ((size, config, attacker), items1) in simulation_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = ['size', 'configuration', 'attacker model', 'source period'] + simulation_results.parameter_names

                    values = [size, config, attacker, src_period] + list(params)

                    (key_names, values, xvalue) = self.remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = self.remove_index(key_names, values, self.vary)

                    key_names = tuple(key_names)
                    values = tuple(values)

                    yvalue = results[ simulation_results.result_names.index(self.yaxis) ]

                    dat.setdefault((key_names, values), {})[(xvalue, vvalue)] = self.yextractor(yvalue)

        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)

    def _create_plot(self, key_names, key_values, values):
        dir_name = os.path.join(self.output_directory, self.result_name, *map(str, key_values))

        print(dir_name)

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


        with open(os.path.join(dir_name, 'graph.p'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')

            graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))
            graph_p.write('set ylabel "{}"\n'.format(self.yaxis_label))
            graph_p.write('set pointsize 1\n')
            graph_p.write('set key {}\n'.format(self.key_position))

            # Should remain the same as we are testing with
            # a limited sized grid of nodes
            graph_p.write('set xrange [{}:{}]\n'.format(min(xvalues) - 1, max(xvalues) + 1))
            graph_p.write('set xtics ({})\n'.format(",".join(map(str, xvalues))))

            #if rangeY is not None:
            #    graph_p.write('set yrange [{0}:{1}]\n'.format(rangeY[0], rangeY[1]))
            #else:
            graph_p.write('set yrange [0:*]\n')
            graph_p.write('set ytics auto\n')
            
            
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
