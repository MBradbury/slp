# The file will set up and produce the folder hierarchy
# that will contain the graphs.
#
# It also produces the files that the graphs are generated from.
#
# Author: Matthew Bradbury

import os
import csv
import shutil
import subprocess

from data.which import which

class Grapher:
    def __init__(self, results_summary_path, output_directory):
        self.results_summary_path = results_summary_path
        self.output_directory = output_directory

    def remove_existing(self):
        # From: http://trac.pythonpaste.org/pythonpaste/attachment/ticket/359/onerror.diff
        # From pathutils by Michael Foord: http://www.voidspace.org.uk/python/pathutils.html
        def onRmtreeError(func, path, exc_info):
            """
            Error handler for ``shutil.rmtree``.
            
            If the error is due to an access error (read only file)
            it attempts to add write permission and then retries.
            
            If the error is for another reason it re-raises the error.
            
            Usage : ``shutil.rmtree(path, onerror=onRmtreeError)``
            
            """
            import stat
            if not os.access(path, os.W_OK):
                # Is the error an access error ?
                os.chmod(path, stat.S_IWUSR)
                func(path)
            else:
                raise

        print('Removing existing directories')

        paths = [ 'Versus', 'Combined', 'HeatMap' ]
        for path in paths:
            full_path = os.path.join(self.output_directory, path)
            if os.path.exists(full_path):
                shutil.rmtree(full_path, onerror=onRmtreeError)

    def read_results(self):
        def extractAverage(value):
            return float(value.split('(')[0])

        self.sizes = set()

        self.results = {}

        print('Opening: {0}'.format(self.results_summary_path))

        with open(self.results_summary_path, 'r') as f:

            seenFirst = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seenFirst:

                    size = int(values[ headers.index('network size') ])
                    srcPeriod = float(values[ headers.index('source period') ])
                    config = values[ headers.index('configuration') ]

                    key = (srcPeriod, config)

                    self.sizes.add(size)

                    # Convert from percentage in the range of [0, 1] to [0, 100]
                    if 'Captured' in headers:
                        self.results.setdefault( 'Captured', {} ).setdefault( key, {} )[ size ] = \
                            float(values[ headers.index('Captured') ]) * 100.0

                    if 'Sent' in headers:
                        self.results.setdefault( 'Sent', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('Sent') ])

                    if 'Received' in headers:
                        self.results.setdefault( 'Received', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('Received') ])
                    if 'Collisions' in headers:
                        self.results.setdefault( 'Collisions', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('Collisions') ])
                    if 'Fake' in headers:
                        self.results.setdefault( 'Fake', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('Fake') ])
                    
                    if 'TFS' in headers:
                        self.results.setdefault( 'TFS', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('TFS') ])
                    if 'PFS' in headers:
                        self.results.setdefault( 'PFS', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('PFS') ])
                    
                    if 'Received Ratio' in headers:
                        self.results.setdefault( 'Received Ratio', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('Received Ratio') ]) * 100.0
                    
                    if 'normal latency' in headers:
                        self.results.setdefault( 'normal latency', {} ).setdefault( key, {} )[ size ] = \
                            extractAverage(values[ headers.index('normal latency') ])
                    
                    if 'sent heatmap' in headers:
                        self.results.setdefault( 'sent heatmap', {} )[ (srcPeriod, size, config) ] = \
                            values[ headers.index('sent heatmap') ]

                    if 'received heatmap' in headers:
                        self.results.setdefault( 'received heatmap', {} )[ (srcPeriod, size, config) ] = \
                            values[ headers.index('received heatmap') ]
                   
                else:
                    seenFirst = True
                    headers = values
                    print(headers)

            self.sizes = sorted(self.sizes)

    def create_plots(self):
        self.remove_existing()
        self.read_results()

        if 'sent heatmap' in self.results:
            self.graphHeatMap("sent")

        if 'received heatmap' in self.results:
            self.graphHeatMap("received")

        if 'Captured' in self.results:
            self.graphVersus(
                self.results['Captured'], 0,
                'PCCaptured', 'Source Period',
                'Percentage Captured', rangeY=(0, '*'))

        if 'Fake' in self.results:
            self.graphVersus(
                self.results['Fake'], 0,
                'FakeMessagesSent', 'Source Period',
                'Messages Sent By Fake Source', rangeY=(0, '*'))

        if 'Collisions' in self.results:
            self.graphVersus(
                self.results['Collisions'], 0,
                'Collisions', 'Source Period',
                'Number of Collisions', rangeY=(0, '*'))

        if 'TFS' in self.results:
            self.graphVersus(
                self.results['TFS'], 0,
                'NumTFS', 'Source Period',
                'Number of TFS', rangeY=(0, '*'))
        if 'PFS' in self.results:
            self.graphVersus(
                self.results['PFS'], 0,
                'NumPFS', 'Source Period',
                'Number of PFS', rangeY=(0, '*'))

        if 'Received Ratio' in self.results:
            self.graphVersus(
                self.results['Received Ratio'], 0,
                'RcvRatio', 'Source Period',
                'Messages Received (%)', rangeY=(0, 100))

        if 'Normal Latency' in self.results:
            self.graphVersus(
                self.results['Normal Latency'], 0,
                'Latency', 'Source Period',
                'Normal Message Latency (seconds)', rangeY=(0, '*'))

    def create_graphs(self):
        def get_gnuplot_binary_name():
            names = ['gnuplot-nox', 'gnuplot']
            for name in names:
                if which(name) is not None:
                    return name

            raise Exception("Could not find gnuplot binary")

        gnuplot = get_gnuplot_binary_name()

        walk_dir = os.path.abspath(self.output_directory)

        for (root, subdirs, files) in os.walk(walk_dir):
            for filename in files:
                (name_without_ext, extension) = os.path.splitext(filename)
                if extension == '.p':
                    pdf_filename = '{}.pdf'.format(name_without_ext)
                    subprocess.call([gnuplot, filename], cwd=root)
                    
                    subprocess.call(['pdfcrop', pdf_filename, pdf_filename], cwd=root)

 
    # From: http://ginstrom.com/scribbles/2007/09/04/pretty-printing-a-table-in-python/
    @staticmethod
    def pprint_table(stream, table):
        def get_max_width(table, index):
            """Get the maximum width of the given column index."""
            return max(len(str(row[index])) for row in table)

        """Prints out a table of data, padded for alignment
        @param stream: Output stream (file-like object)
        @param table: The table to print. A list of lists.
        Each row must have the same number of columns."""

        col_paddings = []

        for i in range(len(table[0])):
            col_paddings.append(get_max_width(table, i))

        for row in table:
            # left col
            stream.write(str(row[0]).ljust(col_paddings[0] + 1))
            
            # rest of the cols
            for i in range(1, len(row)):
                stream.write(str(row[i]).rjust(col_paddings[i] + 2))
            
            stream.write('\n')
            

    # From: http://stackoverflow.com/questions/273192/python-best-way-to-create-directory-if-it-doesnt-exist-for-file-write
    @staticmethod
    def ensureDirExists(d):
        if not os.path.exists(d):
            os.makedirs(d)

    @staticmethod
    def dirNameFromKey(key, value=None):

        dir1 = '/Source-Period-{0}'.format(int(float(key[0]) * 1000.0)) if value != 0 else ''
        dir2 = '/Configuration-{0}'.format(key[1]) if value != 1 else ''
        
        return '.' + dir1 + dir2

    @staticmethod
    def parameterValues(key, value=None):
        """ The result of this must be valid LaTeX!"""

        plural1 = 's' if key[0] != 1 else ''

        general = 'Parameters:\\newline '

        dir1 = 'Source Broadcast Period: every {0} second{1}\\newline '.format(key[0], plural1) if value != 0 else ''
        dir2 = 'Configuration: {0}\\newline '.format(key[1]) if value != 1 else ''

        return general + dir1 + dir2
        
    def graphVersus(self, allvalues, vary, dir, name, labelY, rangeY=None, kind='pdf'):
        print('Creating versus graph files for: {0}'.format(name))
        
        converted = {}
        dirNames = {}
        keyMap = {}

        # Convert the data into a format that is easier to create a table from
        for (key, values) in allvalues.items():
        
            dirName = os.path.join(self.output_directory, 'Versus', dir, name.replace(' ', '-'), self.dirNameFromKey(key, vary))
            
            # Ensure that the dir we want to put the files in
            # actually exists
            self.ensureDirExists(dirName)
            
            # Get the key without the given index in the tuple
            newKey = key[0 : vary] + key[vary + 1 : len(key)]

            keyMap[ newKey ] = key
            dirNames[ newKey ] = dirName
            
            for size in self.sizes:
                if size in values:
                    converted.setdefault( newKey, {} ).setdefault( size , {} )[ key[vary] ] = values[size]
        
        for (key, values) in converted.items():

            keys = sorted(set.union(* [set(v.keys()) for v in values.values()] ))
            columnCount = len(keys)

            # Write our data
            with open(os.path.join(dirNames[key], 'graph.dat'), 'w') as datFile:

                table = [ ['#Size#'] + [ 'Value={0}'.format(header) for header in keys ] ]
                
                # We want to print out rows in the correct
                # size order, so iterate through sizes this way
                for size in [size for size in self.sizes if size in values]:
                    row = [ size ] + [ 
                        values[ size ][ theKey ]
                        if theKey in values[ size ] else '?'
                        for theKey in keys
                    ]

                    table.append( row )
                
                self.pprint_table(datFile, table)
        
        
            with open(os.path.join(dirNames[key], 'graph.p'), 'w') as pFile:

                pFile.write('set xlabel "Network Size"\n')
                pFile.write('set ylabel "{0}"\n'.format(labelY))
                pFile.write('set pointsize 1\n')
                pFile.write('set key right top\n')

                # Should remain the same as we are testing with
                # a limited sized grid of nodes
                pFile.write('set xrange [10:26]\n')
                pFile.write('set xtics (11,15,21,25)\n')

                if rangeY is not None:
                    pFile.write('set yrange [{0}:{1}]\n'.format(rangeY[0], rangeY[1]))
                else:
                    pFile.write('set yrange auto\n')
                    
                pFile.write('set ytics auto\n')
                
                if kind == 'pdf':
                    pFile.write('set terminal pdf enhanced\n')
                    pFile.write('set output "graph.pdf" \n')
                elif kind == 'ps':
                    pFile.write('set terminal postscript enhanced 22\n')
                    pFile.write('set output "graph.ps"\n')
                else:
                    pFile.write('set terminal postscript eps enhanced 22\n')
                    pFile.write('set output "graph.eps"\n')
                
                pFile.write('plot ')

                for x in range(1, columnCount + 1):
                    pFile.write('"graph.dat" u 1:{0} w lp ti "{1}={2}"'.format(x + 1, name, keys[ x - 1 ]))
                    
                    if x != columnCount:
                        pFile.write(', ')
                    
                pFile.write('\n')

            with open(os.path.join(dirNames[key], 'graph.caption'), 'w') as captionFile:
                captionFile.write(self.parameterValues(keyMap[key], vary))
                
    def graphHeatMap(self, name, kind='pdf'):
        def chunks(l, n):
            """ Yield successive n-sized chunks from l."""
            for i in xrange(0, len(l), n):
                yield l[i:i+n]

        print('Creating {} Heat Map graph files'.format(name))

        key = '{} heatmap'.format(name)

        for ((rate, size, config), data) in self.results[key].items():
            dirName = os.path.join(self.output_directory, '{}HeatMap/{}/{}/{}'.format(name.title(), config, rate, size))

            # Ensure that the dir we want to put the files in
            # actually exists
            self.ensureDirExists(dirName)

            data = eval(data)

            array = [0] * (size * size)
            for (k, v) in data.items():
                array[k] = v

            array = list(chunks(array, size))

            with open(os.path.join(dirName, 'graph.p'), 'w') as pFile:
            
                if kind == 'pdf':
                    pFile.write('set terminal pdf enhanced\n')
                    pFile.write('set output "graph.pdf" \n')
                elif kind == 'ps':
                    pFile.write('set terminal postscript enhanced 22\n')
                    pFile.write('set output "graph.ps"\n')
                else:
                    pFile.write('set terminal postscript eps enhanced 22\n')
                    pFile.write('set output "graph.eps"\n')
                    
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
                pFile.write('set cblabel "Messages Sent"\n')
                #pFile.write('unset cbtics\n')

                pFile.write('set view map\n')
                pFile.write('splot \'-\' matrix with image\n')
                
                self.pprint_table(pFile, array)
            
            with open(os.path.join(dirName, 'graph.caption'), 'w') as captionFile:
                captionFile.write('Parameters:\\newline\n')
                captionFile.write('Source Broadcast Rate: every {0} second\\newline\n'.format(rate))
                captionFile.write('Network Size: {0}\\newline\n'.format(size))
                captionFile.write('Configuration: {0}\\newline\n'.format(config))
