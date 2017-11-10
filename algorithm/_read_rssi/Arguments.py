
from simulator.ArgumentsCommon import ArgumentsCommon

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("RSSI", has_safety_period=False)

        self.add_argument("--source-period", type=self.type_positive_float, required=True)
