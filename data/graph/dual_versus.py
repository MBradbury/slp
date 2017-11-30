from __future__ import print_function, division

import os, itertools, math, collections

import data.util
from data import latex
from data.graph.grapher import GrapherBase

import simulator.common

class Grapher(GrapherBase):

    _key_names_base = simulator.common.global_parameter_names

    def __init__(self, output_directory, result_name,
                 xaxis, yaxis1, yaxis2, vary, yextractor=None):

        super(Grapher, self).__init__(output_directory)

        self.result_name = result_name

        self.xaxis = xaxis
        self.yaxis1 = yaxis1
        self.yaxis2 = yaxis2
        self.vary = vary

        self.xaxis_label = xaxis
        self.yaxis1_label = yaxis1
        self.yaxis2_label = yaxis2
        self.vary_label =  vary if not isinstance(vary, collections.Sequence) else "/".join(vary)
        self.vary_prefix = ''

        self.yaxis1_range_max = '*'
        self.yaxis2_range_max = '*'

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

        self.yextractor = yextractor if yextractor is not None else lambda x: x

        self.error_bars = False

        self.generate_legend_graph = False

        self.only_show_yaxis1 = False

    def _value_extractor(self, yvalue):
        if self.error_bars:
            return yvalue
        else:
            return self.yextractor(yvalue)

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

                    (key_names, values, xvalue) = self.remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = self.remove_index(key_names, values, self.vary)

                    yvalue = results[ simulation_results.result_names.index(self.yaxis) ]

                    dat.setdefault((key_names, values), {})[(xvalue, vvalue)] = self._value_extractor(yvalue)

        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values, values)

        self._create_graphs(self.result_name)

    def _write_plot_data(self, dir_name, values, xvalues, vvalues, number):
        with open(os.path.join(dir_name, 'graph{}.dat'.format(number)), 'w') as graph_dat:

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

    def _write_plot_graph(self, dir_name, xvalues, vvalues1, vvalues2):
        with open(os.path.join(dir_name, 'graph.gp'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')

            graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))
            graph_p.write('set ylabel "{}"\n'.format(self.yaxis1_label))
            graph_p.write('set y2label "{}"\n'.format(self.yaxis2_label))
            graph_p.write('set pointsize {}\n'.format(self.point_size))

            if self.nokey:
                graph_p.write('set nokey\n')
            else:
                graph_p.write('set key {}\n'.format(self.key_position))

                if self.key_font is not None:
                    graph_p.write('set key font {}\n'.format(self.key_font))

                if self.key_spacing is not None:
                    graph_p.write('set key spacing {}\n'.format(self.key_spacing))

                if self.key_width is not None:
                    graph_p.write('set key width {}\n'.format(self.key_width))

                if self.key_height is not None:
                    graph_p.write('set key height {}\n'.format(self.key_height))

            if self.xaxis == "network size":
                xvalues_as_num = map(int, xvalues)
                xvalues_padding = 1
            else:
                xvalues_as_num = map(float, xvalues)
                xvalues_padding = 0.1

            # Should remain the same as we are testing with
            # a limited sized grid of nodes
            graph_p.write('set xrange [{}:{}]\n'.format(min(xvalues_as_num) - xvalues_padding, max(xvalues_as_num) + xvalues_padding))
            graph_p.write('set xtics ({})\n'.format(",".join(sorted(xvalues))))

            if self.xaxis_font is not None:
                graph_p.write('set xtics font {}\n'.format(self.xaxis_font))

            graph_p.write('set yrange [0:{}]\n'.format(self.yaxis1_range_max))
            graph_p.write('set ytics auto nomirror\n')

            graph_p.write('set y2range [0:{}]\n'.format(self.yaxis2_range_max))
            graph_p.write('set y2tics auto nomirror\n')

            if self.yaxis_font is not None:
                graph_p.write('set ytics font {}\n'.format(self.yaxis_font))
                graph_p.write('set y2tics font {}\n'.format(self.yaxis_font))

            graph_p.write('set output "graph.pdf"\n')

            plots = []

            def process_vvalues(vvalues, number, axes):
                column_count = len(vvalues)

                if self.error_bars:
                    for x in range(1, column_count + 1):
                        plots.append('"graph{number}.dat" using 1:{ycol}:{errcol} with errorbars title \'{} {}{}\' linewidth {line_width} lc {x}, "" using 1:{ycol} with lines notitle lc {x} axes {axes}'.format(
                            self.vary_label, vvalues[ x - 1 ], self.vary_prefix,
                            number=number, x=x, ycol=x * 2, errcol=x * 2 + 1, line_width=self.line_width, axes=axes))
                else:
                    for x in range(1, column_count + 1):
                        plots.append('"graph{number}.dat" using 1:{ycol} with lp title \'{} {}{}\' linewidth {line_width} axes {axes}'.format(
                            self.vary_label, vvalues[ x - 1 ], self.vary_prefix,
                            number=number, ycol=x + 1, line_width=self.line_width, axes=axes))

            def process_vvalues_boxes(vvalues, number, axes):
                column_count = len(vvalues)

                for x in range(1, column_count + 1):
                    plots.append('"graph{number}.dat" using 1:{ycol} with boxes title \'{} {}{}\' linewidth {line_width} axes {axes}'.format(
                        self.vary_label, vvalues[ x - 1 ], self.vary_prefix,
                        number=number, ycol=x + 1, line_width=self.line_width, axes=axes))

            process_vvalues(vvalues1, 1, "x1y1")

            if not self.only_show_yaxis1:
                process_vvalues(vvalues2, 2, "x1y2")

            graph_p.write('plot {}\n\n'.format(', '.join(plots)))

    def _write_plot_caption(self, dir_name, key_names, key_values):
        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Parameters:\\newline\n')
            for (name, value) in zip(key_names, key_values):
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))

    def _write_legend_plot(self, dir_name, vvalues1, vvalues2):
        with open(os.path.join(dir_name, 'legend.gp'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            total_column_count = len(vvalues1) + len(vvalues2)

            legend_width = 9.8
            legend_height = 0.3 * math.ceil(total_column_count / 3)

            graph_p.write('set terminal pdf enhanced font ",14" size {},{}\n'.format(legend_width, legend_height))

            graph_p.write('set key horizontal\n')

            graph_p.write('set xrange [0 : -1]\n')
            graph_p.write('set yrange [0 : -1]\n')

            graph_p.write('unset border\n')
            graph_p.write('unset tics\n')

            graph_p.write('set output "legend.pdf"\n')

            plots = []

            def process_vvalues(vvalues, number, axes):
                column_count = len(vvalues)

                if self.error_bars:
                    for x in range(1, column_count + 1):
                        plots.append('NaN with errorbars title \'{} {}{}\' linewidth {line_width} lc {x}, "" using 1:{ycol} with lines notitle lc {x} axes {axes}'.format(
                            self.vary_label, vvalues[ x - 1 ], self.vary_prefix,
                            x=x, ycol=x * 2, line_width=self.line_width, axes=axes))
                else:
                    for x in range(1, column_count + 1):
                        plots.append('NaN with lp title \'{} {}{}\' linewidth {line_width} axes {axes}'.format(
                            self.vary_label, vvalues[ x - 1 ], self.vary_prefix,
                            line_width=self.line_width, axes=axes))

            process_vvalues(vvalues1, 1, "x1y1")

            if not self.only_show_yaxis1:
                process_vvalues(vvalues2, 2, "x1y2")

            graph_p.write('plot {}\n\n'.format(', '.join(plots)))

    def _create_plot(self, key_names, key_values, values1, values2):
        dir_name = os.path.join(self.output_directory, self.result_name, *map(str, key_values))

        print("Currently in " + dir_name)

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        xvalues = list({x[0] for x in values1.keys()} | {x[0] for x in values2.keys()})
        vvalues1 = list(self._order_keys({x[1] for x in values1.keys()}))
        vvalues2 = list(self._order_keys({x[1] for x in values2.keys()}))

        # Write our data
        self._write_plot_data(dir_name, values1, xvalues, vvalues1, 1)
        self._write_plot_data(dir_name, values2, xvalues, vvalues2, 2)

        self._write_plot_graph(dir_name, xvalues, vvalues1, vvalues2)

        self._write_plot_caption(dir_name, key_names, key_values)

        if self.generate_legend_graph:
            self._write_legend_plot(dir_name, vvalues1, vvalues2)

    def _order_keys(self, keys):
        """Sort the keys in the order in which they should be displayed in the graph.
        The default is to order them alphabetically."""
        return sorted(keys)
