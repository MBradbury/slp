
import os
import subprocess

import data.util
from data import latex

class GraphSummary:
    def __init__(self, directory, name, graphs_on_page=6):
        self._directory = directory
        self._name = name
        self._graphs_on_page = graphs_on_page
        self._graph_count = 0

        self.width_factor = 0.9
        self.height = None

    def _write_latex_header(self, stream):
        stream.write("\\documentclass[twocolumn]{article}\n")
        stream.write('\\pdfsuppresswarningpagegroup=1\n')
        stream.write("\\usepackage[margin=0.2in,portrait]{geometry}\n")
        stream.write("\\usepackage{graphicx}\n")
        stream.write("\\usepackage{grffile}\n") # Long file names
        stream.write("\\usepackage{morefloats}\n") # More floats with no text
        stream.write("\\usepackage{framed}\n")
        stream.write("\\usepackage{caption}\n")
        stream.write("\\begin{document}\n")

    def _write_latex_footer(self, stream):
        stream.write("\\end{document}\n")

    def _write_image(self, stream, directory, name_without_ext):

        with open(os.path.join(directory, name_without_ext + '.caption')) as caption_file:
            caption = caption_file.read()

        image_path = os.path.join(directory, name_without_ext + '.pdf').replace('\\', '/')

        stream.write("  \\begin{figure}\n")
        stream.write("  \\begin{framed}\n")
        #stream.write("   \\centering\n")

        if self.width_factor:
            stream.write("    \\includegraphics[width={0}\\textwidth]{{{1}}}\n".format(self.width_factor, image_path))
        elif self.height:
            stream.write("    \\includegraphics[height={0}]{{{1}}}\n".format(self.height, image_path))

        stream.write("    \\caption[justification=centering]{{\\small {0} }}\n".format(caption))
        stream.write("  \\end{framed}\n")
        stream.write("  \\end{figure}\n")

        self._graph_count += 1

        if self._graphs_on_page is not None and self._graph_count % self._graphs_on_page == 0:
            stream.write("  \\clearpage\n")

    def create(self):
        with open(self._name + '.tex', 'w') as output_latex:

            self._write_latex_header(output_latex)

            walk_dir = self._directory
            print("Summary: Looking for graphs in {}".format(walk_dir))

            for (root, subdirs, files) in os.walk(walk_dir):
                print(root)
                for filename in files:
                    (name_without_ext, extension) = os.path.splitext(filename)

                    # Do not include the legend graphs in the summary
                    if extension == '.pdf' and name_without_ext != 'legend':
                        print(filename)
                        self._write_image(output_latex, root, name_without_ext)

            self._write_latex_footer(output_latex)


    def compile(self, show=False):
        filename_pdf = latex.compile_document(f'{self._name}.tex')

        if show:
            subprocess.call(["xdg-open", filename_pdf])

    def clean(self):
        extensions = ['.pdf', '.tex']
        for extension in extensions:
            data.util.silent_remove(self._name + extension)

    def run(self, show=False):
        self._graph_count = 0
        self.clean()
        self.create()
        self.compile(show=show)
