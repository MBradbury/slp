from __future__ import print_function

import os.path

import numpy as np

from simulator import Configuration
from simulator.common import global_parameter_names

import data.util
from data import latex
from data.graph.grapher import GrapherBase

class Grapher(GrapherBase):
    def __init__(self, output_directory, results, result_name):
        super(Grapher, self).__init__(output_directory)

        self.results = results
        self.result_name = result_name
        self.result_index = results.result_names.index(result_name)

        # Nice default of blue being cold and red being hot
        self.palette = "rgbformulae 22,13,10"

    def create(self):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        print(self.results.data.keys())

        for (global_params, items1) in self.results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():
                    self._create_plot(global_params, src_period, params, results)

        self._create_graphs(self.result_name)

    def _create_plot(self, global_params, src_period, params, results):
        def chunks(l, n):
            """ Yield successive n-sized chunks from l."""
            for i in range(0, len(l), n):
                yield l[i:i+n]

        # Pop the source period off the end of the parameters
        global_params_dict = dict(zip(global_parameter_names[:-1], global_params))

        config = global_params_dict["configuration"]
        size = int(global_params_dict["network size"])
        distance = float(global_params_dict["distance"])
        nido = global_params_dict["node id order"]

        dat = results[self.result_index]

        # The dat is a (mean, var) pair, so take the mean
        if isinstance(dat, np.ndarray):
            dat = dat[0]

        if not isinstance(dat, dict):
            raise RuntimeError("The data is not a dict. It is a {} with value {}".format(type(dat), dat))

        dir_name = os.path.join(
            self.output_directory,
            self.result_name, *(global_params + (str(src_period),) + tuple(map(str, params))))

        print(dir_name)

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        configuration = Configuration.create_specific(config, size, distance, nido)

        (minx, miny) = configuration.minxy_coordinates()
        (maxx, maxy) = configuration.maxxy_coordinates()

        self._write_plot_data(dir_name, configuration, dat)

        with open(os.path.join(dir_name, 'graph.gp'), 'w') as graph_p:
            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')
            graph_p.write('set output "graph.pdf" \n')
               
            if self.palette is not None:
                graph_p.write('set palette {}\n'.format(self.palette))
        
            #graph_p.write('set title "Heat Map of Messages Sent"\n')
            graph_p.write('unset key\n')
            #graph_p.write('set size ratio 0.5\n')
            #graph_p.write('set tic scale 0\n')
            
            graph_p.write('set xlabel "X Coordinate"\n')
            graph_p.write('set ylabel "Y Coordinate"\n')
            
            graph_p.write('set size square\n')
            
            # To top left to be (0, 0)
            graph_p.write('set xrange [{}:{}]\n'.format(minx, maxx))
            graph_p.write('set xtics auto\n')

            #graph_p.write('set yrange [{}:{}] reverse\n'.format(maxy, miny))
            graph_p.write('set yrange [:] reverse\n')
            graph_p.write('set ytics auto\n')

            graph_p.write('set cbrange [:]\n')
            graph_p.write('set cblabel "{}"\n'.format(self.result_name.title()))

            graph_p.write('set dgrid3d {0},{0}\n'.format(size))
            graph_p.write('set pm3d map interpolate 3,3\n')

            graph_p.write('splot "graph.dat" using 1:2:3 with pm3d\n')
        
        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Parameters:\\newline\n')
            for (name, value) in global_params_dict.items():
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(name.title()), latex.escape(value)))
            for (name, value) in zip(self.results.parameter_names, params):
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))

    def _write_plot_data(self, dir_name, configuration, dat):
        with open(os.path.join(dir_name, 'graph.dat'), 'w') as graph_dat:

            table =  [ ]

            table.append([ '#X', 'Y', 'Z' ])

            for (nid, z) in dat.items():

                (x, y) = configuration.topology.nodes[nid]

                row = [ x, y, z ]

                table.append(row)

            self._pprint_table(graph_dat, table)
