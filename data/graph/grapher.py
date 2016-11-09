# The file will set up and produce the folder hierarchy
# that will contain the graphs.
#
# It also produces the files that the graphs are generated from.
#
# Author: Matthew Bradbury
from __future__ import print_function

import multiprocessing
import os
import re
import subprocess

try:
    from shutil import which
except ImportError:
    from shutilwhich import which

class GrapherBase(object):
    def __init__(self, output_directory):
        self.output_directory = output_directory

    def _create_graphs(self, subdir):
        def get_gnuplot_binary_name():
            names = ['gnuplot-nox', 'gnuplot']
            for name in names:
                if which(name) is not None:
                    return name

            raise RuntimeError("Could not find gnuplot binary")

        def test_gnuplot_version(name):
            result = subprocess.check_output([name, "--version"]).strip()

            match = re.match(r"gnuplot (\d+\.?\d*) patchlevel (.*)", result)
            
            version = float(match.group(1))
            patchlevel = match.group(2)

            if version < 5:
                raise RuntimeError("The gnuplot binary ({}) is too old ({})".format(name, result))

        gnuplot = get_gnuplot_binary_name()

        test_gnuplot_version(gnuplot)

        walk_dir = os.path.abspath(os.path.join(self.output_directory, subdir))

        print("Walking {}:".format(walk_dir))

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
                if extension in {'.p', '.gp', '.gnuplot', '.gnu', '.plot', '.plt'}:
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

    # From: http://ginstrom.com/scribbles/2007/09/04/pretty-printing-a-table-in-python/
    @staticmethod
    def _pprint_table(stream, table):
        """Prints out a table of data, padded for alignment
        @param stream: Output stream (file-like object)
        @param table: The table to print. A list of lists.
        Each row must have the same number of columns."""

        first_len = len(table[0])
        for i, row in enumerate(table):
            if len(row) != first_len:
                raise RuntimeError("The {}th row {} does not have the same length as the first row {}".format(i, row, first_len))

        def get_max_width(table, index):
            """Get the maximum width of the given column index."""
            return max(len(str(row[index])) for row in table)

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

    @staticmethod
    def remove_index(names, values, index_name):
        names = list(names)
        values = list(values)

        idx = names.index(index_name)

        value = values[idx]

        del names[idx]
        del values[idx]

        names = tuple(names)
        values = tuple(values)

        return (names, values, value)
