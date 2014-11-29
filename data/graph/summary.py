import os
import subprocess
import shutil

from data.latex import latex

class GraphSummary:
    def __init__(self, directory, name, graphs_on_page=2):
        self.directory = directory
        self.name = name
        self.graphs_on_page = graphs_on_page
        self.graph_count = 0

    def _write_latex_header(self, stream):
        stream.write("\\documentclass{article}\n")
        stream.write("\\usepackage{fullpage}\n")
        stream.write("\\usepackage[margin=0.25in,landscape]{geometry}\n")
        stream.write("\\usepackage{boxedminipage}\n")
        stream.write("\\usepackage{subfig}\n")
        stream.write("\\usepackage{graphicx}\n")
        stream.write("\\usepackage{grffile}\n")
        stream.write("\\usepackage{morefloats}\n")
        stream.write("\\usepackage{framed}\n")
        stream.write("\\usepackage[justification=centering]{caption}\n")
        stream.write("\\pdfoptionpdfminorversion=5\n")
        stream.write("\\begin{document}\n")

    def _write_latex_footer(self, stream):
        stream.write("\\end{document}\n")

    def _write_image(self, stream, directory, name_without_ext):

        with open(os.path.join(directory, name_without_ext + '.caption')) as caption_file:
            caption = caption_file.read()

        image_path = os.path.join(directory, name_without_ext + '.pdf').replace('\\', '/')

        stream.write("  \\begin{figure}[H]\n")
        stream.write("  \\begin{framed}\n")
        #stream.write("   \\centering"
        stream.write("    \\includegraphics{{{0}}}\n".format(image_path))
        stream.write("    \\caption[justification=centering]{{\\small {0} }}\n".format(caption))
        stream.write("  \\end{framed}\n")
        stream.write("  \\end{figure}\n")

        self.graph_count += 1

        if self.graph_count % self.graphs_on_page == 0:
            stream.write("  \\clearpage\n")

    def create(self):
        with open(self.name + '.tex', 'w') as output_latex:

            self._write_latex_header(output_latex)

            walk_dir = self.directory
            print("Looking for graphs in {}".format(walk_dir))

            for (root, subdirs, files) in os.walk(walk_dir):
                print(root)
                for filename in files:
                    (name_without_ext, extension) = os.path.splitext(filename)
                    if extension == '.pdf':
                        print(filename)
                        self._write_image(output_latex, root, name_without_ext)

            self._write_latex_footer(output_latex)


    def compile(self):
        latex.compile(self.name + '.tex')

    def clean(self):
        extensions = ['.pdf', '.tex']
        for extension in extensions:
            try:
                os.remove(self.name + extension)
            except:
                pass

    def run(self):
        self.graph_count = 0
        self.clean()
        self.create()
        self.compile()
