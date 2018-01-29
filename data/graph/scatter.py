from __future__ import print_function

import os
import itertools

import data.util
from data import latex
from data.graph.grapher import GrapherBase

import simulator.sim

class Grapher(GrapherBase):

    def __init__(self, sim_name, output_directory,
                 result_name, xaxis, yaxis, combine, yextractor=None):

        super(Grapher, self).__init__(sim_name, output_directory)

        self.result_name = result_name

        self.xaxis = xaxis
        self.yaxis = yaxis
        self.combine = combine

        self.yaxis_range_max = '*'

        self.yaxis_font = None
        self.xaxis_font = None

        self.nokey = False
        self.key_position = 'right top'
        self.key_font = None
        self.key_spacing = None
        self.key_width = None
        self.key_height = None

        self.line_width = 1
        self.point_size = 1

        self.error_bars = False

        self.yextractor = yextractor if yextractor is not None else lambda x: x

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

        print(f'Creating {self.result_name} graph files')

        dat = {}

        for (data_key, items1) in simulation_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = self._key_names_base + simulation_results.parameter_names

                    values = list(data_key)
                    values.append(src_period)
                    values.extend(params)

                    (key_names, values, xvalue) = self._remove_index(key_names, values, self.xaxis)

                    cvalues = []
                    for vary in self.combine:
                        (key_names, values, cvalue) = self._remove_index(key_names, values, vary)
                        cvalues.append(cvalue)

                    key_names = tuple(key_names)
                    values = tuple(values)

                    second_key = (xvalue, tuple(cvalues))

                    yvalue = results[ simulation_results.result_names.index(self.yaxis) ]

                    dat.setdefault((key_names, values), {})[second_key] = self.yextractor(yvalue)

        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)

    def _write_plot_data(self, dir_name, values, xvalues, vvalues):
        with open(os.path.join(dir_name, 'graph.dat'), 'w') as graph_dat:

            table =  [ ]

            if self.error_bars:
                table.append([ '#' ] + list(itertools.chain(*[[name, name + "-error"] for name in vvalues])))
            else:
                table.append([ '#' ] + vvalues)

            for xvalue in sorted(xvalues):
                row = [ xvalue ]
                for vvalue in vvalues:
                    yvalue = values.get((xvalue, vvalue), '?')
                    if self.error_bars and yvalue != '?':
                        row.extend(yvalue)
                    else:
                        row.append(yvalue)

                table.append(row)

            self._pprint_table(graph_dat, table)

        return len(vvalues)

    def _write_plot_graph(self, dir_name, xvalues, vvalues):
        with open(os.path.join(dir_name, 'graph.gp'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')

            graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))
            graph_p.write('set ylabel "{}"\n'.format(self.yaxis_label))
            graph_p.write('set pointsize {}\n'.format(self.point_size))

            graph_p.write('set nokey\n')

            xvalues_as_ints = map(int, xvalues)

            # Should remain the same as we are testing with
            # a limited sized grid of nodes
            graph_p.write('set xrange [{}:{}]\n'.format(min(xvalues_as_ints) - 1, max(xvalues_as_ints) + 1))
            graph_p.write('set xtics ({})\n'.format(",".join(sorted(xvalues))))

            if self.xaxis_font is not None:
                graph_p.write('set xtics font {}\n'.format(self.xaxis_font))

            graph_p.write('set yrange [0:{}]\n'.format(self.yaxis_range_max))
            graph_p.write('set ytics auto\n')

            if self.yaxis_font is not None:
                graph_p.write('set ytics font {}\n'.format(self.yaxis_font))

            graph_p.write('set output "graph.pdf"\n')

            plots = []

            column_count = len(vvalues)

            if self.error_bars:
                for x in range(1, column_count + 1):
                    plots.append('"graph.dat" using 1:{ycol}:{errcol} with errorbars linewidth {line_width} lc {x}, "" using 1:{ycol} with lines notitle lc {x}'.format(
                        x=x, ycol=x * 2, errcol=x * 2 + 1, line_width=self.line_width))
            else:
                for x in range(1, column_count + 1):
                    plots.append('"graph.dat" using 1:{ycol} with lp linewidth {line_width}'.format(
                        ycol=x + 1, line_width=self.line_width))

            graph_p.write('plot {}\n\n'.format(', '.join(plots)))

    def _write_plot_caption(self, dir_name, key_names, key_values):
        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Parameters:\\newline\n')
            for (name, value) in zip(key_names, key_values):
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))

    def _create_plot(self, key_names, key_values, values):
        dir_name = os.path.join(self.output_directory, self.result_name, *map(str, key_values))

        print("Currently in " + dir_name)

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        xvalues = list({x[0] for x in values.keys()})
        vvalues = list(self._order_keys({x[1] for x in values.keys()}))

        # Write our data
        self._write_plot_data(dir_name, values, xvalues, vvalues)

        self._write_plot_graph(dir_name, xvalues, vvalues)

        self._write_plot_caption(dir_name, key_names, key_values)

    def _order_keys(self, keys):
        """Sort the keys in the order in which they should be displayed in the graph.
        The default is to order them alphabetically."""
        return sorted(keys)
