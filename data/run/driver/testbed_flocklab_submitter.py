from __future__ import print_function

import base64
from datetime import datetime
import getpass
import importlib
import os
import shlex
import subprocess
from xml.sax.saxutils import escape as escape_xml

import data.testbed.flocklab as flocklab

from simulator import Configuration

class Runner(object):
    required_safety_periods = False

    def __init__(self, duration, dry_run=False):
        self.duration = duration
        self.dry_run = dry_run

    def add_job(self, options, name, estimated_time):
        target_directory = name[:-len(".txt")]

        if not os.path.exists(target_directory):
            raise FileNotFoundError(f"The directory for this job does not exist ({target_directory})")

        options = shlex.split(options)
        module, argv = options[0], options[1:]

        a = self.parse_arguments(module, argv)

        self._submit_job(a, target_directory)

    def mode(self):
        return "TESTBED"

    def testbed_name(self):
        return flocklab.name()

    def _get_platform(self, platform):
        """Get a valid platform to pass to the XML file"""
        if platform == "telosb":
            return "tmote"
        return platform

    def short_name(self, name):
        # Shorten the configuration name
        alg, rest = name.split("/")
        params = rest.split("-")

        # by removing lowercase characters
        params[0] = "".join(x for x in params[0] if not x.islower())

        params = "-".join(params)

        # by removing "_APPROACH"
        params = params.replace("_APPROACH", "")

        short_name = f"{alg}/{params}"

        return short_name

    def generate_configuration_xml(self, configuration, config_file, exe_path, duration, name, **kwargs):

        # See: https://www.flocklab.ethz.ch/wiki/wiki/Public/Man/XmlConfig
        # for the details of the xml config

        short_name = self.short_name(name)

        if len(short_name) > 45:
            raise RuntimeError(f"Name {short_name} too long at {len(short_name)} characters")

        duration_secs = int(duration.total_seconds())
        
        name = escape_xml(name)
        short_name = escape_xml(short_name)

        print('<?xml version="1.0" encoding="UTF-8"?>', file=config_file)
        print('<!-- $Id: flocklab.xml {} {} $ -->'.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S Z%Z"), getpass.getuser()), file=config_file)
        print('', file=config_file)
        print('<testConf xmlns="http://www.flocklab.ethz.ch" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.flocklab.ethz.ch xml/flocklab.xsd">', file=config_file)
        print('    <generalConf>', file=config_file)
        print('        <name>{}</name>'.format(short_name), file=config_file)
        print('        <description>{}</description>'.format(name), file=config_file)
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
        print('        <embeddedImageId>{}</embeddedImageId>'.format(short_name), file=config_file)
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
        print('        <embeddedImageId>{}</embeddedImageId>'.format(short_name), file=config_file)
        print('        <name>{}</name>'.format(short_name), file=config_file)
        print('        <description>{}</description>'.format(name), file=config_file)
        print('        <platform>{}</platform>'.format(platform), file=config_file)
        print('        <os>tinyos</os>', file=config_file)
        print('        <data>{}</data>'.format(encoded_file), file=config_file)
        print('    </imageConf>', file=config_file)

        delayed_boot_secs = flocklab.build_arguments().get("DELAYED_BOOT_TIME_MINUTES", 0) * 60

        print('    <powerProfilingConf>', file=config_file)
        print('        <obsIds>{}</obsIds>'.format(nodes), file=config_file)
        print('        <profConf>', file=config_file)
        print('            <durationMillisecs>{}</durationMillisecs>'.format((duration_secs - delayed_boot_secs) * 1000), file=config_file)
        print('            <relativeTime>', file=config_file)
        print('                <offsetSecs>{}</offsetSecs>'.format(delayed_boot_secs), file=config_file)
        print('                <offsetMicrosecs>0</offsetMicrosecs>', file=config_file)
        print('            </relativeTime>', file=config_file)
        print('            <samplingDivider>{}</samplingDivider>'.format(128), file=config_file)
        print('        </profConf>', file=config_file)
        print('    </powerProfilingConf>', file=config_file)

        # We want to trace the actions of the Led pins for two reasons:
        # 1. To enable GUI support for displaying the Leds
        # 2. Led 2 is used to indicate if the radio is on or off
        print('    <gpioTracingConf>', file=config_file)
        print('        <obsIds>{}</obsIds>'.format(nodes), file=config_file)
        print('        <pinConf>', file=config_file)
        print('            <pin>LED1</pin>', file=config_file)
        print('            <edge>both</edge>', file=config_file)
        print('            <mode>continuous</mode>', file=config_file)
        print('        </pinConf>', file=config_file)
        print('        <pinConf>', file=config_file)
        print('            <pin>LED2</pin>', file=config_file)
        print('            <edge>both</edge>', file=config_file)
        print('            <mode>continuous</mode>', file=config_file)
        print('        </pinConf>', file=config_file)
        print('        <pinConf>', file=config_file)
        print('            <pin>LED3</pin>', file=config_file)
        print('            <edge>both</edge>', file=config_file)
        print('            <mode>continuous</mode>', file=config_file)
        print('        </pinConf>', file=config_file)
        print('    </gpioTracingConf>', file=config_file)

        print('</testConf>', file=config_file)


    def _submit_job(self, a, target_directory):

        # Remove some things to get the name to be shorter
        name = target_directory[len("testbed-"):-len("-real")]
        name = name.replace("ReliableFaultModel__-", "")

        configuration = Configuration.create(a.args.configuration, a.args)

        exe_path = os.path.join(target_directory, "main.exe")
        config_path = os.path.join(target_directory, "flocklab.xml")

        with open(config_path, "w") as config_file:
            self.generate_configuration_xml(configuration, config_file, exe_path,
                name=name,
                duration=self.duration,
            )

        # Check that everything is okay
        command = ["./scripts/flocklab.sh", "-v", config_path]

        print("Checking xml validity:",  " ".join(command))
        validator_output = subprocess.check_output(" ".join(command), shell=True).strip()

        if validator_output != "The file validated correctly.":
            raise RuntimeError(validator_output)

        # Submit the job
        command = ["./scripts/flocklab.sh", "-c", config_path]

        print("Submitting xml job:",  " ".join(command), "for a duration of", self.duration)
        if self.dry_run:
            print("Dry run complete!")
            return

        print(f"Submitting {name}...")
        subprocess.check_call(" ".join(command), shell=True)

    @staticmethod
    def parse_arguments(module, argv):
        arguments_module = importlib.import_module(f"{module}.Arguments")
        a = arguments_module.Arguments()
        a.parse(argv)
        return a
