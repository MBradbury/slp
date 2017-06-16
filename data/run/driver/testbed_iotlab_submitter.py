from __future__ import print_function

import importlib
import os
import shlex
import subprocess

from simulator import Configuration

class Runner(object):
    def __init__(self):
        pass

    def add_job(self, options, name, estimated_time):
        target_directory = name[:-len(".txt")]

        if not os.path.exists(target_directory):
            raise RuntimeError("The directory for this job does not exist ({})".format(target_directory))

        options = shlex.split(options)
        module, argv = options[0], options[1:]

        a = self.parse_arguments(module, argv)

        self._submit_job(a, target_directory)

    def mode(self):
        return "TESTBED"

    def _get_platform(self, platform):
        """Get a valid platform to pass to experiment-cli"""
        if platform in ("wsn430v13", "wsn430v14"):
            return "wsn430"
        return platform

    def _submit_job(self, a, target_directory):

        name = target_directory.replace("/", "_").replace("-", "_")

        configuration = Configuration.create(a.args.configuration, a.args)

        duration_min = 30

        options = {
            "testbed_name": type(configuration.topology).__name__.lower(),
            "platform": self._get_platform(configuration.topology.platform),
            "profile": "Basic", # "wsn430_with_power_1s",
        }

        if configuration.topology.platform == "wsn430v14":
            print("*********************************************************************")
            print("* WARNING: The CC2420 interrupt line from the radio                 *")
            print("* to the MSP430 CPU is not connected on the WSN430v1.4              *")
            print("* hardware on the FIT IoT-Lab. This will prevent it from            *")
            print("* sending messages.                                                 *")
            print("* See: https://github.com/iot-lab/iot-lab/wiki/Hardware_Wsn430-node *")
            print("*********************************************************************")

        command = [
            "experiment-cli", "submit",
            "--name \"{}\"".format(name),
            "--duration {}".format(duration_min),
        ]

        for node in configuration.topology.nodes:
            executable = os.path.join(target_directory, "main-{}.ihex".format(node))

            if not os.path.isfile(executable):
                raise RuntimeError("Could not find '{}'. Did you forget to build the binaries with the --generate-per-node-id-binary options?".format(executable))

            command.append("--list {testbed_name},{platform},{nodes},{executable},{profile}".format(executable=executable, nodes=node, **options))


        print(" ".join(command))
        subprocess.check_call(" ".join(command), shell=True)

    @staticmethod
    def parse_arguments(module, argv):
        arguments_module = importlib.import_module("{}.Arguments".format(module))

        a = arguments_module.Arguments()
        a.parse(argv)
        return a
