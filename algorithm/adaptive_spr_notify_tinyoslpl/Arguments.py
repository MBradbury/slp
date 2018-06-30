
from algorithm.adaptive_spr_notify.Arguments import Arguments as ArgumentsCommon

class Arguments(ArgumentsCommon):
    def __init__(self):
        super().__init__(lpl_parameters_mandatory=True)

    def parse(self, argv):
        super().parse(argv)

        # Need to force these values
        setattr(self.args, "low_power_listening", "enabled")
        #setattr(self.args, "lpl_custom", "SLPDutyCycleC")
