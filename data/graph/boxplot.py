from __future__ import print_function

import os, fnmatch

import data.util
from data.graph.grapher import GrapherBase

class Grapher(GrapherBase):

    def __init__(self, sim_name, output_directory, result_name, parameter_names):

        super(Grapher, self).__init__(sim_name, output_directory)

        self.result_name = result_name
        self.parameter_names = parameter_names

        self.xaxis_label = ""
        self.yaxis_label = ""

        # Nice default of blue being cold and red being hot
        self.palette = "rgbformulae 22,13,10"

        self.yaxis_font = None
        self.xaxis_font = None

    def create(self, analyzer, **kwargs):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print(f'Creating {self.result_name} graph files')

        # The output files we need to process.
        # These are sorted to give anyone watching the output a sense of progress.
        files = sorted(fnmatch.filter(os.listdir(analyzer.results_directory), '*.txt'))

        for infile in files:
            path = os.path.join(analyzer.results_directory, infile)

            analysis = analyzer.analyse_path(path, **kwargs)

            self._create_plot(analysis)

        self._create_graphs(self.result_name)

    def _write_plot_data(self, dir_name, analysis):
        with open(os.path.join(dir_name, 'graph.dat'), 'w') as graph_dat:

            table =  [ ]
            table.append([ '#Value' ])

            values = analysis.columns[self.result_name]

            for value in values:
                table.append([ str(value) ])

            self._pprint_table(graph_dat, table)

    def _write_plot_graph(self, dir_name, analysis):
        with open(os.path.join(dir_name, 'graph.gp'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')
            graph_p.write('set output "graph.pdf"\n')

            graph_p.write('set style boxplot outliers\n')
            graph_p.write('set style data boxplot\n')

            graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))
            graph_p.write('set ylabel "{}"\n'.format(self.yaxis_label))

            if self.palette:
                graph_p.write('set palette {}\n'.format(self.palette))

            graph_p.write('set nokey\n')

            if self.xaxis_font is not None:
                graph_p.write('set xtics font {}\n'.format(self.xaxis_font))

            if self.yaxis_font is not None:
                graph_p.write('set ytics font {}\n'.format(self.yaxis_font))


            #graph_p.write('set xrange [{}:{}]\n'.format(minx, maxx))
            graph_p.write('set xtics auto\n')

            #graph_p.write('set yrange [:] reverse\n'.format(maxy, miny))
            graph_p.write('set ytics auto\n')

            graph_p.write('plot "graph.dat" using (1):1\n')

    def _write_plot_caption(self, dir_name, analysis):
        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            for name in self.parameter_names:
                graph_caption.write('{}: {}\\newline\n'.format(name, analysis.opts[name.replace(" ", "_")]))

    def _create_plot(self, analysis):

        parameters = [analysis.opts[name.replace(" ", "_")] for name in self.parameter_names]

        dir_name = os.path.join(self.output_directory, self.result_name, *parameters)

        print("Currently in " + dir_name)

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        self._write_plot_caption(dir_name, analysis)

        # Write our data
        self._write_plot_data(dir_name, analysis)

        self._write_plot_graph(dir_name, analysis)
