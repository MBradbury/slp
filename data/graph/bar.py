from __future__ import print_function

import collections
import math
import os

import data.util
from data import latex
from data.graph.grapher import GrapherBase

import simulator.common

class Grapher(GrapherBase):

    _key_names_base = simulator.common.global_parameter_names

    def __init__(self, output_directory, result_name, xaxis, yaxis, vary, yextractor=None, xextractor=None, vextractor=None):
        super(Grapher, self).__init__(output_directory)

        self.result_name = result_name

        self.xaxis = xaxis
        self.yaxis = yaxis
        self.vary = vary

        self.xaxis_label = xaxis.title() if isinstance(xaxis, str) or not isinstance(vary, collections.Sequence) else " / ".join(x.title() for x in xaxis)
        self.yaxis_label = yaxis.title()
        self.vary_label =  vary.title()
        self.vary_prefix = ''
        self.vvalue_label_converter = None

        self.yextractor = yextractor if yextractor is not None else lambda x: x
        self.xextractor = xextractor if xextractor is not None else lambda x: x
        self.vextractor = vextractor if vextractor is not None else lambda x: x

        self.error_bars = False

        self.yaxis_font = None
        self.xaxis_font = None

        self.ylabel_font = None
        self.xlabel_font = None

        self.nokey = False
        self.key_position = 'right top'
        self.key_font = None
        self.key_spacing = None
        self.key_width = None
        self.key_height = None

        self.histogram_cluster_gap = None

        self.missing_value_string = '?'

    def _value_extractor(self, yvalue):
        if self.error_bars:
            return yvalue
        else:
            if self.yextractor is None:
                return yvalue
            else:
                return self.yextractor(yvalue)

    def _vvalue_label(self, vvalue_label):
        if self.vvalue_label_converter is not None:
            return latex.escape(self.vvalue_label_converter(vvalue_label))
        else:
            return latex.escape(vvalue_label)

    def create(self, simulation_results):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

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

                    vvalue = self.vextractor(vvalue)

                    dat.setdefault((key_names, values), {})[(xvalue, vvalue)] = self._value_extractor(yvalue)

        return self._build_plots_from_dat(dat)

    def _build_plots_from_dat(self, dat):
        plot_created = False

        for ((key_names, key_values), values) in dat.items():
            plot_created |= self._create_plot(key_names, key_values, values)

        if plot_created:
            self._create_graphs(self.result_name)
        else:
            print("No plots created so not building any graphs")

        return plot_created

    def _create_plot(self, key_names, key_values, values):

        key_values = self._shorten_long_names(key_names, key_values)

        dir_name = os.path.join(self.output_directory, self.result_name, *map(self._sanitize_path_name, key_values))

        print("Currently in {}".format(dir_name))

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        xvalues = list({x[0] for x in values.keys()})
        vvalues = list(self._order_keys({x[1] for x in values.keys()}))

        if len(vvalues) == 0:
            print("WARNING no values to graph for '{}'".format(dir_name))
            return False
        else:
            # Write our data
            self._write_plot_data(dir_name, values, xvalues, vvalues)

            self._write_plot_graph(dir_name, xvalues, vvalues)

            self._write_plot_caption(dir_name, key_names, key_values)

            #if self.generate_legend_graph:
            #    self._write_legend_plot(dir_name, vvalues)

            return True

    def _write_plot_data(self, dir_name, values, xvalues, vvalues):
        with open(os.path.join(dir_name, 'graph.dat'), 'w') as graph_dat:
            table =  [ ]

            if self.error_bars:
                table.append([ '#' ] + list(itertools.chain(*[[name, name + "-error"] for name in vvalues])))
            else:
                table.append([ '#' ] + vvalues)

            for xvalue in sorted(xvalues):
                row = [ self.xextractor(xvalue) ]
                for vvalue in vvalues:
                    yvalue = values.get((xvalue, vvalue), None)

                    if self.error_bars:

                        if yvalue is not None and not isinstance(yvalue, np.ndarray):
                            raise RuntimeError("Cannot display error bars for {} as no stddev is included in the results".format(dir_name))

                        row.extend(yvalue if yvalue is not None else [self.missing_value_string, self.missing_value_string])
                    else:
                        row.append(yvalue if yvalue is not None else self.missing_value_string)

                table.append(row)

            self._pprint_table(graph_dat, table)

        return len(vvalues)

    def _write_plot_graph(self, dir_name, xvalues, vvalues):
        with open(os.path.join(dir_name, 'graph.gp'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')

            if self.xaxis_label is not None:
                graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))

            if self.yaxis_label is not None:
                graph_p.write('set ylabel "{}"\n'.format(self.yaxis_label))

            histogram_cluster_gap = self.histogram_cluster_gap
            if histogram_cluster_gap is None:
                histogram_cluster_gap = int(math.ceil(len(vvalues) / 50))

            graph_p.write('set style data histogram\n')
            graph_p.write('set style histogram cluster gap {}\n'.format(histogram_cluster_gap))
            graph_p.write('set style fill solid border -1\n')

            #graph_p.write('set xtic rotate by -90 scale 0\n')

            if self.ylabel_font is not None:
                graph_p.write('set ylabel font "{}"\n'.format(self.ylabel_font))

            if self.xlabel_font is not None:
                graph_p.write('set xlabel font "{}"\n'.format(self.xlabel_font))

            if self.yaxis_font is not None:
                graph_p.write('set ytics font {}\n'.format(self.yaxis_font))

            if self.xaxis_font is not None:
                graph_p.write('set xtics font {}\n'.format(self.xaxis_font))

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

            # When all data is positive, make sure to include
            # 0 on the y axis.
            graph_p.write('set yrange [0:]\n')

            graph_p.write('set output "graph.pdf"\n')

            plots = []

            column_count = len(vvalues)

            for x in range(1, column_count + 1):
                if self.vary_label:
                    vary_title = "{} {}{}".format(self.vary_label, self._vvalue_label(vvalues[ x - 1 ]), self.vary_prefix)
                else:
                    vary_title = "{}{}".format(self._vvalue_label(vvalues[ x - 1 ]), self.vary_prefix)

                plots.append('"graph.dat" using {ycol}:xticlabels(1) ti "{title}"'.format(ycol=x + 1, title=vary_title))

            graph_p.write('plot {}\n\n'.format(', '.join(plots)))

    def _write_plot_caption(self, dir_name, key_names, key_values):
        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Parameters:\\newline\n')
            for (name, value) in zip(key_names, key_values):
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))

    def _order_keys(self, keys):
        """Sort the keys in the order in which they should be displayed in the graph.
        The default is to order them alphabetically."""
        return sorted(keys)
