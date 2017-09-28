
from simulator import CommunicationModel

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

def available_noise_models():
    """Gets the names of the noise models available in the noise directory"""
    return ("casino-lab", "meyer-heavy", "ttx4-demo")

    # Querying the files is the best approach. But it is expensive, so lets disable it.
    #import glob
    #return [
    #    os.path.splitext(os.path.basename(noise_file))[0]
    #    for noise_file
    #    in glob.glob('models/noise/*.txt')
    #]

def available_communication_models():
    """Gets the names of the communication models available"""
    return CommunicationModel.MODEL_NAME_MAPPING.keys()
