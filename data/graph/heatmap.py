
import os

from grapher import GrapherBase

from data.latex import latex

class Grapher(GrapherBase):
    def __init__(self, results, result_name, output_directory):

        super(Grapher, self).__init__(output_directory)

        self.results = results
        self.result_name = result_name
        self.result_index = results.result_names.index(result_name)

    def create(self):
        self._remove_existing(self.result_name)

        print('Creating {} graph files'.format(self.result_name))

        for ((size, config), items1) in self.results.data.items():
            for (srcPeriod, items2) in items1.items():
                for (params, results) in items2.items():
                    self._create_plot(size, config, srcPeriod, params, results)

        self._create_graphs(self.result_name)

    def _create_plot(self, size, config, srcPeriod, params, results):
        def chunks(l, n):
            """ Yield successive n-sized chunks from l."""
            for i in xrange(0, len(l), n):
                yield l[i:i+n]

        data = results[self.result_index]

        if type(data) is not dict:
            raise RuntimeError("The data is not a dict")

        dirName = os.path.join(self.output_directory, self.result_name, config, str(size), str(srcPeriod), *map(str, params))

        print(dirName)

        # Ensure that the dir we want to put the files in
        # actually exists
        self._ensureDirExists(dirName)

        # Convert to the array
        array = [0] * (size * size)
        for (k, v) in data.items():
            array[k] = v

        array = list(chunks(array, size))

        with open(os.path.join(dirName, 'graph.p'), 'w') as pFile:
        
            pFile.write('set terminal pdf enhanced\n')
            pFile.write('set output "graph.pdf" \n')
                
            pFile.write('set palette rgbformulae 22,13,10\n')
        
            #pFile.write('set title "Heat Map of Messages Sent"\n')
            pFile.write('unset key\n')
            #pFile.write('set size ratio 0.5\n')
            pFile.write('set tic scale 0\n')
            
            pFile.write('set xlabel "X Coordinate"\n')
            pFile.write('set ylabel "Y Coordinate"\n')
            
            
            # To top left to be (0, 0)
            pFile.write('set yrange [0:{0}] reverse\n'.format(size - 1))
            pFile.write('set xrange [0:{0}]\n'.format(size - 1))
            
            pFile.write('set cbrange []\n')
            pFile.write('set cblabel "{}"\n'.format(self.result_name))
            #pFile.write('unset cbtics\n')

            pFile.write('set view map\n')
            pFile.write('splot \'-\' matrix with image\n')
            
            self._pprint_table(pFile, array)
        
        with open(os.path.join(dirName, 'graph.caption'), 'w') as captionFile:
            captionFile.write('Parameters:\\newline\n')
            captionFile.write('Source Period: {0} second\\newline\n'.format(srcPeriod))
            captionFile.write('Network Size: {0}\\newline\n'.format(size))
            captionFile.write('Configuration: {0}\\newline\n'.format(config))
            for (name, value) in zip(self.results.parameter_names, params):
                captionFile.write('{}: {}\\newline\n'.format(latex.escape(name), latex.escape(value)))
