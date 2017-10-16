from __future__ import print_function, division

import unittest

import subprocess

def run_simulation(attacker_model):

    command = "./run.py algorithm.adaptive_spr tossim SINGLE -cm low-asymmetry -nm meyer-heavy -ns 11 -c SourceCorner -safety 50 --source-period 1 --approach PB_FIXED1_APPROACH -am \"{}\" --seed 44".format(
            attacker_model)

    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    (stdoutdata, stderrdata) = proc.communicate()

    return stdoutdata

class TestDeafReactiveAndProactiveAttackerEquivalent(unittest.TestCase):

    def test_equivalent(self):
        out_without_event = run_simulation("DeafAttacker()")
        out_with_event = run_simulation("DeafAttackerWithEvent(period=1)")

        self.assertEqual(out_without_event, out_with_event)

if __name__ == "__main__":
    unittest.main()
