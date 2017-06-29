from __future__ import print_function, division

from collections import OrderedDict
import glob
import os.path
import unittest

import subprocess

def result_parameter_to_input_parameter(param_name):
    return "--" + param_name.replace("_", "-")

def run_simulation(name, parameters):

    # Get rid of mode if it is present
    # The mode option was removed recently, so many old results still generate it.
    parameters.pop("mode", None)

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
    revision = None

    result = []

    for line in lines:
        # Remove newline at end of line
        line = line.strip()

        # Skip comments
        if line.startswith('//'):
            continue

        # Read revision
        elif line.startswith('@'):
            revision = line[1:]

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

            result.append((revision, params, values))
            params = OrderedDict()
            values = {}
            header = None
            revision = None

        # Blank line
        else:
            continue

    return result

def find_tests():

    tests = OrderedDict()

    for filename in sorted(glob.glob("tests/historical/*.txt")):
        algorithm_name = os.path.splitext(os.path.basename(filename))[0]

        params = {}
        values = {}

        header = None

        with open(filename, 'r') as infile:
            tests[algorithm_name] = parse_result_output(infile)

    return tests

# From: http://eli.thegreenplace.net/2011/08/02/python-unit-testing-parametrized-test-cases
class ParametrizedTestCase(unittest.TestCase):
    """ TestCase classes that want to be parametrized should
        inherit from this class.
    """
    def __init__(self, methodName='runTest', param=None):
        super(ParametrizedTestCase, self).__init__(methodName)
        self.param = param

    @staticmethod
    def parametrize(testcase_klass, param=None):
        """ Create a suite containing all tests taken from the given
            subclass, passing them the parameter 'param'.
        """
        testloader = unittest.TestLoader()
        testnames = testloader.getTestCaseNames(testcase_klass)
        suite = unittest.TestSuite()
        for name in testnames:
            suite.addTest(testcase_klass(name, param=param))
        return suite

class TestBackwardsCompatibility(ParametrizedTestCase):

    def test_backwards_compatibility(self):
        (revision, algorithm_name, params, expected_value) = self.param

        ident = "{} on {} -> {}".format(algorithm_name, revision, " ".join("{}={}".format(k, v) for (k, v) in params.items()))

        print("Running test for {}".format(ident))

        output, err_output = run_simulation(algorithm_name, params)

        self.assertFalse(len(output) == 0, ident + "\n" + err_output)

        (rev, run_params, run_value) = parse_result_output(output.splitlines())[0]

        self.assertDictContainsSubset(params, run_params)
        self.assertDictContainsSubset(expected_value, run_value)

def suite():
    suite = unittest.TestSuite()

    tests = find_tests()

    for (algorithm_name, algorithm_tests) in tests.items():

        for (revision, params, expected_value) in algorithm_tests:

            param = (revision, algorithm_name, params, expected_value)

            suite.addTest(ParametrizedTestCase.parametrize(TestBackwardsCompatibility, param=param))

    return suite

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
