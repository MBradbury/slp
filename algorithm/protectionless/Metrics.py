
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    # Debugging to check that only Normal messages are sent and received
    """def process_BCAST(self, line):
        if not line.startswith("Normal"):
            kind = line.split(",")[0]
            raise RuntimeError("Unknown message type of {}".format(kind))

        super(Metrics, self).process_BCAST(line)

    def process_RCV(self, line):
        if not line.startswith("Normal"):
            kind = line.split(",")[0]
            raise RuntimeError("Unknown message type of {}".format(kind))

        super(Metrics, self).process_RCV(line)"""

    @staticmethod
    def items():
        d = MetricsCommon.items()
        return d
