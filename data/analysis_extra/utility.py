
import math

class Function(object):
    dr = 0

    @staticmethod
    def linear_funtion(k, value, x0):
        return k*value + x0

    @classmethod
    def utility_cr_linear(cls, k, value, x0, dr):
        if cls.linear_funtion(k, value/dr, x0) < 0:
            return 0.0
        elif cls.linear_funtion(k, value/dr, x0) > 1:
            return 1.0
        else:
            return cls.linear_funtion(k, value/dr, x0)

    @classmethod
    def utility_dr_linear(cls, k, value, x0, dr):
        if cls.linear_funtion(k, value, x0) < 0:
            return 0.0
        elif cls.linear_funtion(k, value, x0) > 1:
            return 1.0
        else:
            return cls.linear_funtion(k, value, x0)

    @classmethod
    def utility_lat_linear(cls, k, value, x0, dr):
        if cls.linear_funtion(k, value, x0) < 0:
            return 0.0
        elif cls.linear_funtion(k, value, x0) > 1:
            return 1.0
        else:
            return cls.linear_funtion(k, value, x0)

    @classmethod
    def utility_msg_linear(cls, k, value, x0, dr):
        if cls.linear_funtion(k, value/dr, x0) < 0:
            return 0.0
        elif cls.linear_funtion(k, value/dr, x0) > 1:
            return 1.0
        else:
            return cls.linear_funtion(k, value/dr, x0)

    @staticmethod
    def sigmoid_funtion(k, value, x0):
        return 1.0 / (1.0 + math.exp(k * (-value - x0)))

    @classmethod
    def utility_cr_sigmoid(cls, k, value, x0, dr):
        return cls.sigmoid_funtion(k, -value/dr, x0)

    @classmethod
    def utility_dr_sigmoid(cls, k, value, x0, dr):
        return cls.sigmoid_funtion(k, value, x0)

    @classmethod
    def utility_lat_sigmoid(cls, k, value, x0, dr):
        return cls.sigmoid_funtion(k, -value, x0)

    @classmethod
    def utility_msg_sigmoid(cls, k, value, x0, dr):
        return cls.sigmoid_funtion(k, -value/dr, x0)

    @classmethod
    def utility_of(cls, name, function_type):
        if name == "Captured" and function_type == "Sigmoid":
            return cls.utility_cr_sigmoid
        elif name == "Captured" and function_type == "Linear":
            return cls.utility_cr_linear

        elif name == "ReceiveRatio" and function_type == "Sigmoid":
            return cls.utility_dr_sigmoid
        elif name == "ReceiveRatio" and function_type == "Linear":
            return cls.utility_dr_linear

        elif name == "NormalLatency" and function_type == "Sigmoid":
            return cls.utility_lat_sigmoid
        elif name == "NormalLatency" and function_type == "Linear":
            return cls.utility_lat_linear

        elif name == "norm(Sent,TimeTaken)" and function_type == "Sigmoid":
            return cls.utility_msg_sigmoid
        else:
            return cls.utility_msg_linear

    @classmethod
    def utility(cls, x, parameters):
        for (name,param, function_type) in parameters:
            if name == "ReceiveRatio":
                cls.dr =  x.average_of[name]

        #print "$$dr = {}$$".format(cls.dr)
        #for (name,param,function_type) in parameters:
        #    print "***utility of {}({}) is :{}(raw data: {})***".format(name, function_type, cls.utility_of(name, function_type)(param.k, x.average_of[name], param.x0, cls.dr), x.average_of[name])

        return sum(
            param.weight * cls.utility_of(name, function_type)(param.k, x.average_of[name], param.x0, cls.dr)
            for (name, param, function_type)
            in parameters
        )

class LinearParameters(object):
    def __init__(self, k, x0, weight):
        self.k = k
        self.x0 = x0
        self.weight = weight

class SigmoidParameters(object):
    def __init__(self, k, x0, weight):
        self.k = k
        self.x0 = x0
        self.weight = weight

# Sigmoid parameters used for SRDS 2017 journal extension (FGCS)

class AnimalProtection(object):
    cr = SigmoidParameters(k=50.0, x0=0.1, weight=0.4)         # ranges from [0, 1], non-linear
    dr = LinearParameters(k=1.0, x0=0.0, weight=0.2)       # ranges from [0, 1], linear
    lat = LinearParameters(k=-0.5, x0=1.0, weight=0.2)          # scale is in seconds, linear
    msg = LinearParameters(k=-0.0005, x0=1.0, weight=0.2)  # message send numbers, linear

class AssetMonitoring(object):
    cr = LinearParameters(k=-1.0, x0=1.0, weight=0.2)       #linear
    dr = SigmoidParameters(k=20.0, x0=-0.8, weight=0.4)      #non-linear
    lat = LinearParameters(k=-0.5, x0=1.0, weight=0.1)      #linear
    msg = SigmoidParameters(k=0.01, x0=400.0, weight=0.3)    #non-linear

class Military(object):
    cr = SigmoidParameters(k=50.0, x0=0.1, weight=0.4)      #non-linear
    dr = SigmoidParameters(k=20.0, x0=-0.8, weight=0.25)    #non-linear
    lat = SigmoidParameters(k=10.0, x0=0.5, weight=0.25)    #non-linear
    msg = LinearParameters(k=-0.0005, x0=1.0, weight=0.1)  #linear
