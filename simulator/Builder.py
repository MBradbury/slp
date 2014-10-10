
import subprocess

def build(directory, **kwargs):

	flags = " ".join("-D{}={}".format(k, v) for (k, v) in kwargs.items())

	command = 'make micaz sim CFLAGS="{}"'.format(flags)

	print(command)

	subprocess.call(
		command,
		cwd=directory,
		shell=True
		)
