
import math

class Linear(object):
    @staticmethod
    def utility_star(value, cutoff):
        if value >= cutoff:
            return 0.0
        else:
            return 1.0 - (value / cutoff)

    @staticmethod
    def utility_deliv(value, cutoff):
        if value <= cutoff:
            return 0.0
        else:
            return (value - cutoff) / (100 - cutoff)

    @classmethod
    def utility_of(cls, name):
        if name == "ReceiveRatio":
            return cls.utility_deliv
        else:
            return cls.utility_star

    @classmethod
    def utility(cls, x, parameters):
        return sum(
            param.weight * cls.utility_of(name)(x.average_of[name], param.cutoff)
            for (name, param)
            in parameters
        )

class Sigmoid(object):

    @staticmethod
    def sigmoid_funtion(k, value, x0):
        return 1.0 / (1.0 + math.exp(k * (-value - x0)))

    @classmethod
    def utility_dr(cls, k, value, x0, u_dr):
        return cls.sigmoid_funtion(k, value, x0)

    @classmethod
    def utility_star(cls, k, value, x0, u_dr):
        if u_dr == 0:
            return 0.0
        else:
            return cls.sigmoid_funtion(k, -value, x0)

    @classmethod
    def utility_of(cls, name):
        if name == "ReceiveRatio":
            return cls.utility_dr
        else:
            return cls.utility_star

    @classmethod
    def utility(cls, x, parameters):
        u_dr = 0
        for (name, param) in parameters:
            if name == "ReceiveRatio":
                u_dr = cls.utility_dr(param.k, x.average_of[name], param.x0, u_dr)
        
        #for (name, k, x0, cutoff, weight) in parameters:
        #    print "utility of {}: {}".format(name, cls.utility_of(name)(k, x.average_of[name], x0, cutoff, r_dr, cutoff_dr))

        return sum(
            param.weight * cls.utility_of(name)(param.k, x.average_of[name], param.x0, u_dr)
            for (name, param)
            in parameters
        )

class LinearParameters(object):
    def __init__(self, cutoff, weight):
        self.cutoff = cutoff
        self.weight = weight

class SigmoidParameters(object):
    def __init__(self, k, x0, weight):
        self.k = k
        self.x0 = x0
        self.weight = weight

# Linear parameters used in the SRDS 2017 paper submission

class EqualLinear(object):
    cr = LinearParameters(50, 0.25)
    dr = LinearParameters(50, 0.25)
    lat = LinearParameters(500, 0.25)
    msg = LinearParameters(500, 0.25)

class HabitatLinear(object):
    cr = LinearParameters(50, 0.3)
    dr = LinearParameters(50, 0.3)
    lat = LinearParameters(500, 0.1)
    msg = LinearParameters(500, 0.3)

class BattleLinear(object):
    cr = LinearParameters(10, 0.25)
    dr = LinearParameters(80, 0.25)
    lat = LinearParameters(200, 0.4)
    msg = LinearParameters(200, 0.1)

# Sigmoid parameters used for SRDS 2017 journal extension (FGCS)

class AnimalProtectionSigmoid(object):
    cr = SigmoidParameters(k=25.0, x0=0.15, weight=0.7)         # ranges from [0, 1]
    dr = SigmoidParameters(k=8.0, x0=-0.5, weight=0.1)       # ranges from [0, 1]
    lat = SigmoidParameters(k=2.0, x0=2.5, weight=0.1)          # scale is in seconds
    msg = SigmoidParameters(k=0.005, x0=1000, weight=0.1)  # message send numbers

class AssetMonitoringSigmoid(object):
    cr = SigmoidParameters(k=8.0, x0=0.5, weight=0.1)       
    dr = SigmoidParameters(k=20.0, x0=-0.75, weight=0.7)       
    lat = SigmoidParameters(k=2.0, x0=2.5, weight=0.1)     
    msg = SigmoidParameters(k=0.005, x0=1000.0, weight=0.1)  

class BattleSigmoid(object):
    cr = SigmoidParameters(k=8.0, x0=0.5, weight=0.1)
    dr = SigmoidParameters(k=20.0, x0=-0.75, weight=0.4)
    lat = SigmoidParameters(k=8.0, x0=0.5, weight=0.4)
    msg = SigmoidParameters(k=0.005, x0=1000.0, weight=0.1)
