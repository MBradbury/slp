
import os

from grapher import GrapherBase

from data import latex

class Grapher(GrapherBase):
    def __init__(self, output_directory, results, result_name, xaxis, yaxis, vary, yextractor = lambda x: x):

        super(Grapher, self).__init__(output_directory)

        self.results = results
        self.result_name = result_name

        self.xaxis = xaxis
        self.yaxis = yaxis
        self.vary = vary

        self.yextractor = yextractor

    def create(self):

        def remove_index(names, values, index_name):
            idx = names.index(index_name)

            value = values[idx]

            del names[idx]
            del values[idx]

            return (names, values, value)


        self._remove_existing(self.result_name)

        print('Creating {} graph files'.format(self.result_name))

        data = {}

        for ((size, config), items1) in self.results.data.items():
            for (srcPeriod, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = ['size', 'configuration', 'source period'] + self.results.parameter_names

                    #print(key_names)

                    values = [size, config, srcPeriod] + list(params)

                    (key_names, values, xvalue) = remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = remove_index(key_names, values, self.vary)

                    key_names = tuple(key_names)
                    values = tuple(values)

                    yvalue = results[ self.results.result_names.index(self.yaxis) ]

                    data.setdefault((key_names, values), {})[(xvalue, vvalue)] = self.yextractor(yvalue)

        for ((key_names, key_values), values) in data.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)

    def _create_plot(self, key_names, key_values, values):
        dirName = os.path.join(self.output_directory, self.result_name, *map(str, key_values))

        print(dirName)

        # Ensure that the dir we want to put the files in actually exists
        self._ensureDirExists(dirName)

        # Write our data
        with open(os.path.join(dirName, 'graph.dat'), 'w') as datFile:

            xvalues = list({x[0] for x in values.keys()})
            vvalues = list(sorted({x[1] for x in values.keys()}))

            table =  [ [ '#' ] + vvalues ]

            for xvalue in sorted(xvalues):
                row = [ xvalue ]
                for vvalue in vvalues:
                    row.append(values.get((xvalue, vvalue), '?'))

                table.append(row)

            self._pprint_table(datFile, table)

        columnCount = len(vvalues)


        with open(os.path.join(dirName, 'graph.p'), 'w') as pFile:

            pFile.write('#!/usr/bin/gnuplot\n')

            pFile.write('set terminal pdf enhanced\n')

            pFile.write('set xlabel "{}"\n'.format(self.xaxis))
            pFile.write('set ylabel "{}"\n'.format(self.yaxis))
            pFile.write('set pointsize 1\n')
            pFile.write('set key right top\n')

            # Should remain the same as we are testing with
            # a limited sized grid of nodes
            pFile.write('set xrange [{}:{}]\n'.format(min(xvalues) - 1, max(xvalues) + 1))
            pFile.write('set xtics ({})\n'.format(",".join(map(str, xvalues))))

            #if rangeY is not None:
            #    pFile.write('set yrange [{0}:{1}]\n'.format(rangeY[0], rangeY[1]))
            #else:
            pFile.write('set yrange [0:*]\n')
            pFile.write('set ytics auto\n')
            
            
            pFile.write('set output "graph.pdf"\n')
            
            plots = []

            for x in range(1, columnCount + 1):
                plots.append('"graph.dat" u 1:{} w lp ti "{}={}"'.format(x + 1, self.vary, vvalues[ x - 1 ]))

            pFile.write('plot {}\n\n'.format(', '.join(plots)))
        

        with open(os.path.join(dirName, 'graph.caption'), 'w') as captionFile:
            captionFile.write('Parameters:\\newline\n')
            for (name, value) in zip(key_names, key_values):
                captionFile.write('{}: {}\\newline\n'.format(latex.escape(str(name)), latex.escape(str(value))))
