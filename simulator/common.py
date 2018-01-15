
# Parameters that all simulations must have
# The source period must come last
global_parameter_names = ('network size', 'configuration',
                          'attacker model', 'noise model',
                          'communication model', 'fault model',
                          'distance', 'node id order',
                          'latest node start time',
                          'source period')

testbed_missing_global_parameter_names = {"network size", "noise model", "communication model", "distance", "node id order", "latest node start time"}

testbed_global_parameter_names = tuple(name for name in global_parameter_names if name not in testbed_missing_global_parameter_names)
