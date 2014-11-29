from __future__ import print_function

import os, re, subprocess

def print_header(stream):
    print('\\documentclass[a4paper,notitlepage]{article}', file=stream)
    print('\\usepackage[margin=0.5cm]{geometry}', file=stream)
    print('\\usepackage{multirow}', file=stream)
    print('\\usepackage{boxedminipage}', file=stream)
    print('\\usepackage{float}', file=stream)
    print('\\usepackage{subfigure}', file=stream)
    print('\\usepackage{graphicx}', file=stream)
    print('\\usepackage{epstopdf}', file=stream)
    print('\\usepackage[table]{xcolor}', file=stream)
    print('\\usepackage{longtable}', file=stream)
    print('', file=stream)
    print('% For comparison results', file=stream)
    print('\\newcommand{\\goodcolour}{\\cellcolor[rgb]{0.57,0.82,0.31}}', file=stream)
    print('\\newcommand{\\badcolour}{\\cellcolor[rgb]{1,0.75,0}}', file=stream)
    print('', file=stream)
    print('\\begin{document}', file=stream)

def print_footer(stream):
    print('\\end{document}', file=stream)

def compile(path_and_name, executable="pdflatex -interaction=nonstopmode"):
    (path, name_with_ext) = os.path.split(path_and_name)
    (name_without_ext, ext) = os.path.splitext(name_with_ext)

    try:
        os.remove(os.path.join(path, name_without_ext + ".pdf"))
    except:
        pass

    try:
        command = "{} {}".format(executable, path_and_name)

        subprocess.call(command, shell=True)

    finally:
        exts_to_remove = [".log", ".aux", ".dvi", ".out", ".synctex.gz"]
        for ext_to_remove in exts_to_remove:
            try:
                os.remove(os.path.join(path, name_without_ext + ext_to_remove))
            except:
                pass

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
    regex = re.compile('|'.join(re.escape(unicode(key)) for key in sorted(conv.keys(), key = lambda item: - len(item))))
    return regex.sub(lambda match: conv[match.group()], text)
