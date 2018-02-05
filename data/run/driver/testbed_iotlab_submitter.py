
import math
import os
import shlex
import subprocess

from simulator import Configuration

import algorithm

import data.testbed.fitiotlab as fitiotlab

class Runner(object):
    required_safety_periods = False
    
    def __init__(self, duration, dry_run=False):
        self.duration = duration
        self.dry_run = dry_run

    def add_job(self, options, name, estimated_time):
        target_directory = name[:-len(".txt")]

        if not os.path.exists(target_directory):
            raise RuntimeError(f"The directory for this job does not exist ({target_directory})")

        options = shlex.split(options)
        module, argv = options[0], options[1:]

        a = self.parse_arguments(module, argv)

        self._submit_job(a, target_directory)

    def mode(self):
        return "TESTBED"

    def testbed_name(self):
        return fitiotlab.name()

    def _get_platform(self, platform):
        """Get a valid platform to pass to experiment-cli"""
        if platform in ("wsn430v13", "wsn430v14"):
            return "wsn430"
        return platform

    def _submit_job(self, a, target_directory):

        name = target_directory[len("testbed-"):-len("-real")]
        name = name.replace("/", "-")

        configuration = Configuration.create(a.args.configuration, a.args)

        duration_min = int(math.ceil(self.duration.total_seconds() / 60))

        testbed_name = type(configuration.topology).__name__.lower()

        platform = self._get_platform(configuration.topology.platform)
        profile = "wsn430_with_power"

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

        # Need to get a shorter name
        experiment_name = name.replace("ReliableFaultModel__-", "").replace("topology-", "")

        command = [
            "iotlab-experiment", "submit",
            f"--name \"{experiment_name}\"",
            f"--duration {duration_min}",
        ]

        # Send this script to be executed
        # It will start the serial aggregator automatically and
        # gather the output from the nodes
        aggregator_script = "data/testbed/info/fitiotlab/aggregator.sh"

        # If the site supports executing the aggregator script, then just have it run it.
        # Otherwise, we need to find another site to run the script on.
        if configuration.topology.support_script_execution:
            command.append(f"--site-association \"{testbed_name},script={aggregator_script}\"")
        else:
            raise RuntimeError(f"The site {testbed_name} does not support script execution")

        for node in configuration.topology.nodes:
            executable = os.path.join(target_directory, f"main-{node}.ihex")

            if not os.path.isfile(executable):
                raise RuntimeError(f"Could not find '{executable}'. Did you forget to build the binaries with the --generate-per-node-id-binary options?")

            command.append(f"--list {testbed_name},{platform},{node},{executable}")

        print(" ".join(command))

        if self.dry_run:
            print("Dry run complete!")
            return
        
        print(f"Submitting {name} to {testbed_name}...")
        subprocess.check_call(" ".join(command), shell=True)

    @staticmethod
    def parse_arguments(module, argv):
        arguments_module = algorithm.import_algorithm(module, extras=["Arguments"])

        a = arguments_module.Arguments.Arguments()
        a.parse(argv)
        return a
