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
import multiprocessing

from data.which import which

class GrapherBase(object):
    def __init__(self, output_directory):
        self.output_directory = output_directory

    def _remove_existing(self, subdir):
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

        full_path = os.path.join(self.output_directory, subdir)
        if os.path.exists(full_path):
            shutil.rmtree(full_path, onerror=onRmtreeError)

    def _create_graphs(self, subdir):
        def get_gnuplot_binary_name():
            names = ['gnuplot-nox', 'gnuplot']
            for name in names:
                if which(name) is not None:
                    return name

            raise RuntimeError("Could not find gnuplot binary")

        gnuplot = get_gnuplot_binary_name()

        walk_dir = os.path.abspath(os.path.join(self.output_directory, subdir))

        print(walk_dir)

        def worker(queue):
            while True:
                item = queue.get()

                if item is None:
                    return

                (args1, args2, root) = item

                subprocess.check_call(args1, cwd=root)
                subprocess.check_call(args2, cwd=root)

        nprocs = multiprocessing.cpu_count()

        queue = multiprocessing.Queue()
        pool = multiprocessing.Pool(nprocs, worker, (queue,))

        for (root, subdirs, files) in os.walk(walk_dir):
            for filename in files:
                (name_without_ext, extension) = os.path.splitext(filename)
                if extension == '.p':
                    pdf_filename = '{}.pdf'.format(name_without_ext)

                    queue.put((
                        [gnuplot, filename],
                        ['pdfcrop', pdf_filename, pdf_filename],
                        root))

        # Push the queue sentinel
        for i in range(nprocs):
            queue.put(None)

        queue.close()
        queue.join_thread()

        pool.close()
        pool.join()

    # From: http://stackoverflow.com/questions/273192/python-best-way-to-create-directory-if-it-doesnt-exist-for-file-write
    @staticmethod
    def _ensureDirExists(d):
        if not os.path.exists(d):
            os.makedirs(d)

    # From: http://ginstrom.com/scribbles/2007/09/04/pretty-printing-a-table-in-python/
    @staticmethod
    def _pprint_table(stream, table):
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

"""
class Grapher:
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

    @staticmethod
    def dirNameFromKey(key, value=None):

        dir1 = '/Source-Period-{0}'.format(int(float(key[0]) * 1000.0)) if value != 0 else ''
        dir2 = '/Configuration-{0}'.format(key[1]) if value != 1 else ''
        
        return '.' + dir1 + dir2

    @staticmethod
    def parameterValues(key, value=None):
        "" " The result of this must be valid LaTeX!"" "

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
"""
