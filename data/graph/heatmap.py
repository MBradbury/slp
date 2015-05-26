from __future__ import print_function

import os

import data.util
from data import latex
from data.graph.grapher import GrapherBase

class Grapher(GrapherBase):
    def __init__(self, output_directory, results, result_name):

        super(Grapher, self).__init__(output_directory)

        self.results = results
        self.result_name = result_name
        self.result_index = results.result_names.index(result_name)

    def create(self):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        for ((size, config, attacker), items1) in self.results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():
                    self._create_plot(size, config, attacker, src_period, params, results)

        self._create_graphs(self.result_name)

    def _create_plot(self, size, config, attacker, src_period, params, results):
        def chunks(l, n):
            """ Yield successive n-sized chunks from l."""
            for i in xrange(0, len(l), n):
                yield l[i:i+n]

        dat = results[self.result_index]

        if not isinstance(dat, dict):
            raise RuntimeError("The data is not a dict")

        dir_name = os.path.join(
            self.output_directory,
            self.result_name, config, attacker,
            str(size), str(src_period), *map(str, params))

        print(dir_name)

        # Ensure that the dir we want to put the files in
        # actually exists
        data.util.create_dirtree(dir_name)

        # Convert to the array
        array = [0] * (size * size)
        for (k, v) in dat.items():
            array[k] = v

        array = list(chunks(array, size))

        with open(os.path.join(dir_name, 'graph.p'), 'w') as graph_p:
        
            graph_p.write('set terminal pdf enhanced\n')
            graph_p.write('set output "graph.pdf" \n')
                
            graph_p.write('set palette rgbformulae 22,13,10\n')
        
            #graph_p.write('set title "Heat Map of Messages Sent"\n')
            graph_p.write('unset key\n')
            #graph_p.write('set size ratio 0.5\n')
            graph_p.write('set tic scale 0\n')
            
            graph_p.write('set xlabel "X Coordinate"\n')
            graph_p.write('set ylabel "Y Coordinate"\n')
            
            
            # To top left to be (0, 0)
            graph_p.write('set yrange [0:{0}] reverse\n'.format(size - 1))
            graph_p.write('set xrange [0:{0}]\n'.format(size - 1))
            
            graph_p.write('set cbrange []\n')
            graph_p.write('set cblabel "{}"\n'.format(self.result_name))
            #graph_p.write('unset cbtics\n')

            graph_p.write('set view map\n')
            graph_p.write('splot \'-\' matrix with image\n')
            
            self._pprint_table(graph_p, array)
        
        with open(os.path.join(dir_name, 'graph.caption'), 'w') as graph_caption:
            graph_caption.write('Parameters:\\newline\n')
            graph_caption.write('Source Period: {0} second\\newline\n'.format(src_period))
            graph_caption.write('Network Size: {0}\\newline\n'.format(size))
            graph_caption.write('Configuration: {0}\\newline\n'.format(config))
            graph_caption.write('Attacker Model: {0}\\newline\n'.format(attacker))
            for (name, value) in zip(self.results.parameter_names, params):
                graph_caption.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))
