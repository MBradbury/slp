from __future__ import print_function

import os

import data.util
from data.graph.grapher import GrapherBase

class Grapher(GrapherBase):

    def __init__(self, output_directory, result_name, zextractor):

        super(Grapher, self).__init__(output_directory)

        self.result_name = result_name

        self.xaxis_label = ""
        self.yaxis_label = ""
        self.cb_label = ""

        # Nice default of blue being cold and red being hot
        self.palette = "rgbformulae 22,13,10"

        self.dgrid3d_dimensions = ""

        self.yaxis_font = None
        self.xaxis_font = None

        self.nokey = False
        self.key_position = 'right top'
        self.key_font = None
        self.key_spacing = None
        self.key_width = None
        self.key_height = None

        self.zextractor = zextractor

    def create(self, configurations):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print(f'Creating {self.result_name} graph files')

        for configuration in configurations:
            self._create_plot(configuration)

        self._create_graphs(self.result_name)

    def _write_plot_data(self, dir_name, coords):
        with open(os.path.join(dir_name, 'graph.dat'), 'w') as graph_dat:

            table =  [ ]

            table.append([ '#X', 'Y', 'Z' ])

            for ((x, y), z) in coords.items():
                row = [ x, y, z ]

                table.append(row)

            self._pprint_table(graph_dat, table)

    def _write_points_data(self, dir_name, configuration):

        def write_id_table(ids, filename):
            id_coords = []
            for iid in ids:
                (x, y) = configuration.topology.nodes[iid]
                id_coords.append((iid, x, y))

            with open(os.path.join(dir_name, filename), 'w') as graph_dat:
                table =  [ ]
                table.append([ '#X', 'Y' ])

                for (iid, x, y) in id_coords:
                    table.append([ x, y ])

                self._pprint_table(graph_dat, table)

        write_id_table(configuration.source_ids, 'source_points.dat')
        write_id_table([configuration.sink_id], 'sink_points.dat')

    def _write_plot_graph(self, dir_name, configuration):
        (minx, miny) = configuration.minxy_coordinates()
        (maxx, maxy) = configuration.maxxy_coordinates()

        with open(os.path.join(dir_name, 'graph.gp'), 'w') as graph_p:

            graph_p.write('#!/usr/bin/gnuplot\n')

            graph_p.write('set terminal pdf enhanced\n')
            graph_p.write('set output "graph.pdf"\n')

            graph_p.write('set xlabel "{}"\n'.format(self.xaxis_label))
            graph_p.write('set ylabel "{}"\n'.format(self.yaxis_label))
            graph_p.write('set cblabel "{}" rotate by 90\n'.format(self.cb_label))

            if self.palette:
                graph_p.write('set palette {}\n'.format(self.palette))

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


            if self.xaxis_font is not None:
                graph_p.write('set xtics font {}\n'.format(self.xaxis_font))

            if self.yaxis_font is not None:
                graph_p.write('set ytics font {}\n'.format(self.yaxis_font))

            if self.cbrange is not None:
                graph_p.write('set cbrange [{}:{}]\n'.format(self.cbrange[0], self.cbrange[1]))


            graph_p.write('set xrange [{}:{}]\n'.format(minx, maxx))
            graph_p.write('set xtics auto\n')

            #graph_p.write('set yrange [{}:{}] reverse\n'.format(maxy, miny))
            graph_p.write('set yrange [:] reverse\n')
            graph_p.write('set ytics auto\n')


            graph_p.write('set size square\n')

            # Craziness about to ensue!
            # (see: https://stackoverflow.com/questions/23559606/draw-a-line-over-dgrid3d-and-pm3d)
            # We cannot draw the points correctly with dgrid3d enabled
            # So dump the points to an external file first,
            # then disable dgrid3d,
            # finally draw both the heatmap and points!

            graph_p.write('set table "map.grid"\n')
            graph_p.write('set dgrid3d {}\n'.format(self.dgrid3d_dimensions))
            graph_p.write('splot "graph.dat" using 1:2:3\n')

            graph_p.write('unset table\n')
            graph_p.write('unset dgrid3d\n')

            graph_p.write('set pm3d map interpolate 4,4\n')

            graph_p.write('splot "map.grid" with pm3d, ' +
                          '"source_points.dat" using 1:2:(0.0) with points pointsize 2 linewidth 3 pointtype 1 linecolor rgb "black", ' +
                          '"sink_points.dat" using 1:2:(0.0) with points pointsize 2 linewidth 3 pointtype 2 linecolor rgb "black" ' +
                          '\n')

    def _write_plot_caption(self, dir_name, configuration):
        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Configuration: {}\n'.format(configuration.__class__.__name__))

    def _create_plot(self, configuration):
        dir_name = os.path.join(self.output_directory, self.result_name, configuration.__class__.__name__)

        print("Currently in " + dir_name)

        # Ensure that the dir we want to put the files in actually exists
        data.util.create_dirtree(dir_name)

        coords = {}

        for (nid, (x, y)) in configuration.topology.nodes.items():
            
            coords[(x, y)] = self.zextractor(configuration, nid)

        self._write_plot_caption(dir_name, configuration)

        # Write our data
        self._write_plot_data(dir_name, coords)

        self._write_points_data(dir_name, configuration)

        self._write_plot_graph(dir_name, configuration)
