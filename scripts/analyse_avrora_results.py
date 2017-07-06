#!/usr/bin/env python

from __future__ import print_function, division

import re

NODE_RESULT_RE = re.compile(r"""
=={ Energy consumption results for node (\d+) }=*
Node lifetime: (\d+) cycles,\s*(.+) seconds

CPU: (.+) Joule
   Active: (.+) Joule, (\d+) cycles
   Idle: (.+) Joule, (\d+) cycles
   ADC Noise Reduction: (.+) Joule, (\d+) cycles
   Power Down: (.+) Joule, (\d+) cycles
   Power Save: (.+) Joule, (\d+) cycles
   RESERVED 1: (.+) Joule, (\d+) cycles
   RESERVED 2: (.+) Joule, (\d+) cycles
   Standby: (.+) Joule, (\d+) cycles
   Extended Standby: (.+) Joule, (\d+) cycles

Yellow: (.+) Joule
   off: (.+) Joule, (\d+) cycles
   on: (.+) Joule, (\d+) cycles

Green: (.+) Joule
   off: (.+) Joule, (\d+) cycles
   on: (.+) Joule, (\d+) cycles

Red: (.+) Joule
   off: (.+) Joule, (\d+) cycles
   on: (.+) Joule, (\d+) cycles

Radio: (.+) Joule
   Power Off:\s*: (.+) Joule, (\d+) cycles
   Power Down:\s*: (.+) Joule, (\d+) cycles
   Idle:\s*: (.+) Joule, (\d+) cycles
   Receive \(Rx\):\s*: (.+) Joule, (\d+) cycles
   Transmit \(Tx\):\s*(\d+):\s*: (.+) Joule, (\d+) cycles

SensorBoard: (.+) Joule
   on:\s*: (.+) Joule, (\d+) cycles

flash: (.+) Joule
   standby: (.+) Joule, (\d+) cycles
   read: (.+) Joule, (\d+) cycles
   write: (.+) Joule, (\d+) cycles
   load: (.+) Joule, (\d+) cycles
""")


class JouleAndCycles(object):
    __slots__ = ('joule', 'cycles')

    def __init__(self, joule, cycles):
        self.joule = joule
        self.cycles = cycles

class NodeEnergy:
    def __init__(self, match):
        self.nid = int(match[0])

        self.node_lifetime_cycles = float(match[1])
        self.node_lifetime_seconds = float(match[2])

        self.cpu_joules = float(match[3])

        self.cpu_active = JouleAndCycles(float(match[4]), float(match[5]))
        self.cpu_idle = JouleAndCycles(float(match[6]), float(match[7]))
        self.cpu_adc_noise_reduction = JouleAndCycles(float(match[8]), float(match[9]))
        self.cpu_power_down = JouleAndCycles(float(match[10]), float(match[11]))
        self.cpu_power_save = JouleAndCycles(float(match[12]), float(match[13]))
        self.cpu_reserved1 = JouleAndCycles(float(match[14]), float(match[15]))
        self.cpu_reserved2 = JouleAndCycles(float(match[16]), float(match[17]))
        self.cpu_standby = JouleAndCycles(float(match[18]), float(match[19]))
        self.cpu_extended_standby = JouleAndCycles(float(match[20]), float(match[21]))

        self.yellow_led_joules = float(match[22])
        self.yellow_led_off = JouleAndCycles(float(match[23]), float(match[24]))
        self.yellow_led_on = JouleAndCycles(float(match[25]), float(match[26]))

        self.green_led_joules = float(match[27])
        self.green_led_off = JouleAndCycles(float(match[28]), float(match[29]))
        self.green_led_on = JouleAndCycles(float(match[30]), float(match[31]))

        self.red_led_joules = float(match[32])
        self.red_led_off = JouleAndCycles(float(match[33]), float(match[34]))
        self.red_led_on = JouleAndCycles(float(match[35]), float(match[36]))

        self.radio_joules = float(match[37])
        self.radio_power_off = JouleAndCycles(float(match[38]), float(match[39]))
        self.radio_power_down = JouleAndCycles(float(match[40]), float(match[41]))
        self.radio_idle = JouleAndCycles(float(match[42]), float(match[43]))
        self.radio_receive = JouleAndCycles(float(match[44]), float(match[45]))
        self.radio_transmit_num = float(match[46])
        self.radio_transmit = JouleAndCycles(float(match[47]), float(match[48]))

        self.sensor_board_joules = float(match[49])
        self.sensor_board_on = JouleAndCycles(float(match[50]), float(match[51]))

        self.flash_joules = float(match[52])
        self.flash_standby = JouleAndCycles(float(match[53]), float(match[54]))
        self.flash_read = JouleAndCycles(float(match[55]), float(match[56]))
        self.flash_write = JouleAndCycles(float(match[57]), float(match[58]))
        self.flash_load = JouleAndCycles(float(match[59]), float(match[60]))

    def total_joules(self):
        return self.cpu_joules + self.yellow_led_joules + self.red_led_joules + \
               self.green_led_joules + self.radio_joules + self.sensor_board_joules + \
               self.flash_joules

    def cpu_active_percent(self):
        return self.cpu_active.cycles / self.node_lifetime_cycles

    def radio_active_percent(self):
        return (self.node_lifetime_cycles - (self.radio_power_off.cycles + self.radio_power_down.cycles)) / self.node_lifetime_cycles

class EnergyResults:
    def __init__(self, file):

        self.results = {}

        inp = file.read()

        matches = NODE_RESULT_RE.findall(inp)

        for match in matches:
            current = NodeEnergy(match)
            self.results[current.nid] = current

if __name__ == '__main__':
    import sys

    path = sys.argv[1]

    with open(path, 'r') as file:
        results = EnergyResults(file)

    for result in results.results.values():
        print(result.nid, result.total_joules(), result.cpu_active_percent(), result.radio_active_percent())
