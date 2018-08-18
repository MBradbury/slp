from __future__ import print_function

import os
import re
import subprocess

import data.util

def print_header(stream, orientation='portrait'):
    """Print the document header which imports required packages."""

    geometry_args = "margin=0.5cm"

    if orientation == 'landscape':
        geometry_args += ",landscape"

    print('\\documentclass[a4paper,notitlepage]{article}', file=stream)
    print('\\pdfsuppresswarningpagegroup=1', file=stream)
    print('\\usepackage[{}]{{geometry}}'.format(geometry_args), file=stream)
    print('\\usepackage{multirow}', file=stream)
    print('\\usepackage{boxedminipage}', file=stream)
    print('\\usepackage{float}', file=stream)
    print('\\usepackage{subfigure}', file=stream)
    print('\\usepackage{graphicx}', file=stream)
    print('\\usepackage{epstopdf}', file=stream)
    print('\\usepackage{siunitx}\\sisetup{separate-uncertainty}', file=stream)
    print('\\usepackage{amsfonts}', file=stream)
    print('\\usepackage[table]{xcolor}', file=stream)
    print('\\usepackage{longtable}', file=stream)
    print('\\usepackage{tabu}', file=stream)
    print("\\usepackage{grffile}", file=stream) # Long file names
    print("\\usepackage{morefloats}", file=stream) # More floats with no text
    print('', file=stream)
    print('% For comparison results', file=stream)
    print('\\newcommand{\\goodcolour}{\\cellcolor[rgb]{0.57,0.82,0.31}}', file=stream)
    print('\\newcommand{\\badcolour}{\\cellcolor[rgb]{1,0.75,0}}', file=stream)
    print('', file=stream)
    print('\\begin{document}', file=stream)

def print_footer(stream):
    """Prints the document footer which ends the document."""
    print('\\end{document}', file=stream)

def compile_document(path_and_name, executable="pdflatex -interaction=nonstopmode"):
    """Compile the latex document at :path_and_name:.
    Extra outputs other than the pdf will be removed."""
    (path, name_with_ext) = os.path.split(path_and_name)
    (name_without_ext, ext) = os.path.splitext(name_with_ext)

    if not path:
        path = "."

    pdf_name = os.path.join(path, name_without_ext + ".pdf")

    data.util.silent_remove(pdf_name)

    try:
        command = f"{executable} -output-directory=\"{path}\" \"{path_and_name}\""
        print(command)
        subprocess.check_call(command, shell=True)

    finally:
        exts_to_remove = (".log", ".aux", ".dvi", ".out", ".synctex.gz")

        for ext_to_remove in exts_to_remove:
            data.util.silent_remove(os.path.join(path, name_without_ext + ext_to_remove))

    return pdf_name

def escape(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX

        :from: http://stackoverflow.com/questions/16259923/how-can-i-escape-latex-special-characters-inside-django-templates/25875504#25875504
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }

    regex = re.compile('|'.join(re.escape(key)
                                for key
                                in sorted(conv.keys(), key=lambda item: - len(item))))

    return regex.sub(lambda match: conv[match.group()], str(text))
