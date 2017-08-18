from __future__ import division, print_function

import importlib
import math
import os
import shlex
import subprocess

from simulator import Configuration

class Runner(object):
    def __init__(self, duration, dry_run=False):
        self.duration = duration
        self.dry_run = dry_run

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

        duration_min = int(math.ceil(self.duration.total_seconds() / 60))

        testbed_name = type(configuration.topology).__name__.lower()

        options = {
            "testbed_name": testbed_name,
            "platform": self._get_platform(configuration.topology.platform),
            "profile": "wsn430_with_power",
        }

        if configuration.topology.platform == "wsn430v13":
            print("*********************************************************************")
            print("* WARNING: The CC1101 interrupt line from the radio                 *")
            print("* to the MSP430 CPU is not connected on the wsn430v13               *")
            print("* hardware on the FIT IoT-Lab. This will prevent it from            *")
            print("* sending messages.                                                 *")
            print("* See: https://github.com/iot-lab/iot-lab/wiki/Hardware_Wsn430-node *")
            print("* This website says that the CC2420 is affected, but I have only    *")
            print("* observed this with wsn430v13 and the wsn430v14 seems to work.     *")
            print("*********************************************************************")

        # Need to make sure a valid profile exists
        try:
            command = ["profile-cli", "get", "--name \"{}\"".format(options["profile"])]
            subprocess.check_output(" ".join(command), shell=True, stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as ex:
            if "doesn't exist" in ex.output:
                print("Profile doesn't exist, creating it now...")

                command = [
                    "profile-cli", "addwsn430",
                    "--name \"{}\"".format(options["profile"]),
                    "--power dc", # Power the node using dc (alternative is battery)
                    "-cfreq 1000", "-power", "-current", "-voltage", # Take these power measurements every 100ms
                    "-rfreq 500" # Take RSSI measurements every 500 ms
                ]
                subprocess.check_call(" ".join(command), shell=True)

                print("Profile Created!")

            else:
                raise


        command = [
            "experiment-cli", "submit",
            "--name \"{}\"".format(name),
            "--duration {}".format(duration_min),
        ]

        # Send this script to be executed
        # It will start the serial aggregator automatically and
        # gather the output from the nodes
        aggregator_script = "data/testbed/info/fitiotlab/aggregator.sh"

        # If the site supports executing the aggregator script, then just have it run it.
        # Otherwise, we need to find another site to run the script on.
        if configuration.topology.support_script_execution:
            command.append("--site-association \"{},script={}\"".format(testbed_name, aggregator_script))
        else:
            raise RuntimeError("The site {} does not support script execution".format(testbed_name))

        for node in configuration.topology.nodes:
            executable = os.path.join(target_directory, "main-{}.ihex".format(node))

            if not os.path.isfile(executable):
                raise RuntimeError("Could not find '{}'. Did you forget to build the binaries with the --generate-per-node-id-binary options?".format(executable))

            command.append("--list {testbed_name},{platform},{nodes},{executable},{profile}".format(executable=executable, nodes=node, **options))


        print(" ".join(command))
        if self.dry_run:
            print("Dry run complete!")
            return
        
        subprocess.check_call(" ".join(command), shell=True) 

    @staticmethod
    def parse_arguments(module, argv):
        arguments_module = importlib.import_module("{}.Arguments".format(module))

        a = arguments_module.Arguments()
        a.parse(argv)
        return a
