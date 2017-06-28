from __future__ import print_function

import base64
from datetime import datetime
import getpass
import importlib
import os
import shlex
import subprocess

from simulator import Configuration

class Runner(object):
    def __init__(self, dry_run=False):
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
        """Get a valid platform to pass to the XML file"""
        if platform in ("telosb",):
            return "tmote"
        return platform

    def generate_configuration_xml(self, configuration, config_file, exe_path, duration=None, **options):

        # See: https://www.flocklab.ethz.ch/wiki/wiki/Public/Man/XmlConfig
        # for the details of the xml config

        # Convert the duration in minutes to seconds
        duration_secs = duration * 60

        print('<?xml version="1.0" encoding="UTF-8"?>', file=config_file)
        print('<!-- $Id: flocklab.xml {} {} $ -->'.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S Z%Z"), getpass.getuser()), file=config_file)
        print('', file=config_file)
        print('<testConf xmlns="http://www.flocklab.ethz.ch" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.flocklab.ethz.ch xml/flocklab.xsd">', file=config_file)
        print('    <generalConf>', file=config_file)
        print('        <name>{name}</name>'.format(**options), file=config_file)
        print('        <description>SLP Simulation</description>', file=config_file)
        print('        <scheduleAsap>', file=config_file)
        print('            <durationSecs>{}</durationSecs>'.format(duration_secs), file=config_file)
        print('        </scheduleAsap>', file=config_file)
        print('        <emailResults>yes</emailResults>', file=config_file)
        print('    </generalConf>', file=config_file)

        nodes = configuration.topology.node_ids()

        print('    <targetConf>', file=config_file)
        print('        <obsIds>{}</obsIds>'.format(nodes), file=config_file)
        print('        <targetIds>{}</targetIds>'.format(nodes), file=config_file)
        print('        <voltage>3.3</voltage>', file=config_file)
        print('        <embeddedImageId>{name}</embeddedImageId>'.format(**options), file=config_file)
        print('    </targetConf>', file=config_file)        

        # serialConf tests show:
        # - Do not use the serial port, serial out is over usb

        print('    <serialConf>', file=config_file)
        print('        <obsIds>{}</obsIds>'.format(nodes), file=config_file)
        print('        <port>usb</port>', file=config_file)
        print('        <baudrate>115200</baudrate>', file=config_file)
        print('        <mode>ascii</mode>', file=config_file)
        print('    </serialConf>', file=config_file)

        with open(exe_path, "rb") as exe_file:
            encoded_file = base64.b64encode(exe_file.read())

        platform = self._get_platform(configuration.topology.platform)

        print('    <imageConf>', file=config_file)
        print('        <embeddedImageId>{name}</embeddedImageId>'.format(**options), file=config_file)
        print('        <name>{name}</name>'.format(**options), file=config_file)
        print('        <description>{name}</description>'.format(**options), file=config_file)
        print('        <platform>{}</platform>'.format(platform), file=config_file)
        print('        <os>tinyos</os>', file=config_file)
        print('        <data>{}</data>'.format(encoded_file), file=config_file)
        print('    </imageConf>', file=config_file)

        print('</testConf>', file=config_file)


    def _submit_job(self, a, target_directory):

        name = target_directory.replace("/", "_").replace("-", "_")

        # Remove some things to get the name to be shorter
        name = name[len("testbed_"):-len("_real")].replace("ReliableFaultModel__", "")

        configuration = Configuration.create(a.args.configuration, a.args)

        exe_path = os.path.join(target_directory, "main.exe")
        config_path = os.path.join(target_directory, "flocklab.xml")

        duration = 20 # in minutes

        with open(config_path, "w") as config_file:
            self.generate_configuration_xml(configuration, config_file, exe_path,
                name=name,
                duration=duration,
            )

        # Check that everything is okay
        command = ["./scripts/flocklab.sh", "-v", config_path]

        print("Checking xml validity: ",  " ".join(command))
        validator_output = subprocess.check_output(" ".join(command), shell=True).strip()

        if validator_output != "The file validated correctly.":
            raise RuntimeError(validator_output)

        # Submit the job
        command = ["./scripts/flocklab.sh", "-c", config_path]

        print("Submitting xml job: ",  " ".join(command))
        if not self.dry_run:
            subprocess.check_call(" ".join(command), shell=True)
        else:
            print("Dry run complete!")

    @staticmethod
    def parse_arguments(module, argv):
        arguments_module = importlib.import_module("{}.Arguments".format(module))

        a = arguments_module.Arguments()
        a.parse(argv)
        return a
