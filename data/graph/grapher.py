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
        """Prints out a table of data, padded for alignment
        @param stream: Output stream (file-like object)
        @param table: The table to print. A list of lists.
        Each row must have the same number of columns."""

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
