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

import simulator.Attacker as Attacker
import simulator.FaultModel as FaultModel

def test_gnuplot_version(name):
    result = subprocess.check_output([name, "--version"]).strip()

    match = re.match(r"gnuplot (\d+\.?\d*) patchlevel (.*)", result)
    
    version = float(match.group(1))
    patchlevel = match.group(2)

    return version >= 5
    
def test_gnuplot_pdfterm_support(name):
    try:
        result = subprocess.check_output([name, "-e", "set terminal pdf"]).strip()

        # As long as result is empty everything was fine
        return result == ""

    except subprocess.CalledProcessError:
        return False

def get_gnuplot_binary_name():
    possible_names = ('gnuplot5-nox', 'gnuplot-nox', 'gnuplot')

    no_pdf_support = False
    version_too_old = False

    for name in possible_names:
        if which(name) is not None:

            if not test_gnuplot_pdfterm_support(name):
                version_too_old = True
                continue

            if not test_gnuplot_pdfterm_support(name):
                no_pdf_support = True
                continue

            return name

    if no_pdf_support:
        raise RuntimeError("No gnuplot binary could be found that supports the pdf terminal.") 

    elif version_too_old:
        raise RuntimeError("Could not find gnuplot 5 or later. You need to install it by doing something like 'sudo apt-get install gnuplot5-nox' and adding 'non-free' to your /etc/apt/sources.list.")

    else:
        raise RuntimeError("Could not find the gnuplot binary")

class GrapherBase(object):
    def __init__(self, output_directory):
        self.output_directory = output_directory

    @staticmethod
    def _shorten_long_names(key_names, key_values):
        # Some of these values get much too long
        very_long_parameter_names = {
            'attacker model': Attacker.eval_input,
            'fault model': FaultModel.eval_input,
        }

        key_values = list(key_values)

        for (long_name, creator) in very_long_parameter_names.items():
            index = key_names.index(long_name)

            long_string = key_values[index]
            key_values[index] = creator(long_string).short_name()

        return tuple(key_values)

    @staticmethod
    def _sanitize_path_name(name):
        name = str(name)

        chars = "'\""

        for char in chars:
            name = name.replace(char, "_")

        return name

    def _create_graphs(self, subdir):
        gnuplot = get_gnuplot_binary_name()

        walk_dir = os.path.abspath(os.path.join(self.output_directory, subdir))

        print("Walking {}:".format(walk_dir))

        def worker(inqueue, outqueue):
            while True:
                item = inqueue.get()

                if item is None:
                    return

                (args1, args2, root) = item

                try:
                    out = subprocess.check_output(args1, cwd=root, stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as ex:
                    outqueue.put((args1, root, None, ex))
                    raise RuntimeError("Failed to {} in '{}'".format(args2, root), ex)

                try:
                    out = subprocess.check_output(args2, cwd=root, stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as ex:
                    outqueue.put((args2, root, None, ex))
                    raise RuntimeError("Failed to {} in '{}'".format(args2, root), ex)

        nprocs = multiprocessing.cpu_count()

        inqueue = multiprocessing.Queue()
        outqueue = multiprocessing.Queue()

        pool = multiprocessing.Pool(nprocs, worker, (inqueue, outqueue))

        for (root, subdirs, files) in os.walk(walk_dir):
            for filename in files:
                (name_without_ext, extension) = os.path.splitext(filename)
                if extension in {'.p', '.gp', '.gnuplot', '.gnu', '.plot', '.plt'}:
                    pdf_filename = '{}.pdf'.format(name_without_ext)

                    inqueue.put((
                        [gnuplot, filename],
                        ['pdfcrop', pdf_filename, pdf_filename],
                        root))

        # Push the queue sentinel
        for i in range(nprocs):
            inqueue.put(None)

        inqueue.close()
        inqueue.join_thread()

        pool.close()
        pool.join()

        # Check if an exception was thrown and rethrow it
        if outqueue.qsize() > 0:
            #(msg, ex) = outqueue.get(False)
            raise RuntimeError("An error occurred while building the graphs. Please inspect previous exceptions.")

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
    def remove_index(names, values, index_name, allow_missing=False):
        names = list(names)
        values = list(values)

        if not isinstance(index_name, (tuple, list)):
            index_name = (index_name,)

        value = []

        for name in index_name:

            try:
                idx = names.index(name)

                value.append(values[idx])

                del names[idx]
                del values[idx]
            except:
                if not allow_missing:
                    raise ValueError("'{}' is not in list {}".format(index_name, names))

        names = tuple(names)
        values = tuple(values)
        value = value[0] if len(value) == 1 else tuple(value)

        return (names, values, value)
