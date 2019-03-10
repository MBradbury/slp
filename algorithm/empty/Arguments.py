
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("Empty", has_safety_period=False)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
