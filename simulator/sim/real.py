
def parsers():
    return [
        ("SINGLE", None, ["verbose", "debug", "configuration",
                          "fault model", "node id order",
                          "low power listening", "cc2420"]),
    ]

# Parameters that all simulations must have
# The source period must come last
global_parameter_names = ('configuration',
                          'attacker model', 'fault model',
                          'node id order',
                          'rf power', 'channel',
                          'low power listening',
                          'source period')

def build(module, a):
    pass

def print_version():
    pass
