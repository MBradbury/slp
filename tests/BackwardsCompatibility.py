from __future__ import print_function, division

from collections import OrderedDict
import glob
import os.path
import unittest

import subprocess

def result_parameter_to_input_parameter(param_name):
    return "--" + param_name.replace("_", "-")

def run_simulation(name, parameters):

    parameters_string = " ".join("{}={}".format(result_parameter_to_input_parameter(name), repr(value)) for (name, value) in parameters.items())

    command = "./run.py algorithm.{} SINGLE {}".format(name, parameters_string)

    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    (stdoutdata, stderrdata) = proc.communicate()

    return (stdoutdata, stderrdata)

# Some results are unstable no matter the seed.
# Do not check these results
results_to_skip = {"WallTime"}

def parse_result_output(lines):

    params = OrderedDict()
    values = {}
    header = None

    result = []

    for line in lines:
        # Remove newline at end of line
        line = line.strip()

        # Skip comments
        if line.startswith('//'):
            continue

        # Header line
        elif line.startswith('#'):
            header = line[1:].split('|')

        # Parameter lines
        elif '=' in line:
            (name, value) = line.split('=', 1)
            params[name] = value

        # Data line
        elif len(line) != 0:
            for (name, value) in zip(header, line.split('|')):
                if name not in results_to_skip:
                    values[name] = value

            result.append((params, values))
            params = OrderedDict()
            values = {}
            header = None

        # Blank line
        else:
            continue

    return result

class TestBackwardsCompatibility(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        tests = {}

        for filename in glob.glob("tests/historical/*.txt"):
            algorithm_name = os.path.splitext(os.path.basename(filename))[0]

            params = {}
            values = {}

            header = None

            with open(filename, 'r') as infile:
                tests[algorithm_name] = parse_result_output(infile)

        cls.tests = tests

    def test_backwards_compatibility(self):
        for (algorithm_name, algorithm_tests) in self.tests.items():

            print("Starting to test {}...".format(algorithm_name))

            for (params, expected_value) in algorithm_tests:

                print("Running test for {}".format(" ".join("{}={}".format(k, v) for (k, v) in params.items())))

                output, err_output = run_simulation(algorithm_name, params)

                self.assertFalse(len(output) == 0, err_output)

                (run_params, run_value) = parse_result_output(output.splitlines())[0]

                self.assertDictContainsSubset(params, run_params)
                self.assertDictContainsSubset(expected_value, run_value)

            print()

if __name__ == "__main__":
    unittest.main()
