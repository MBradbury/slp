from __future__ import division

import random
from math import log10
from itertools import islice

import numpy as np
from scipy.spatial.distance import euclidean

# Need to use the same java prng to maintain backwards compatibility
# with existing results
from _TOSSIM import JavaRandom as Random


class CommunicationModel(object):
    def __init__(self, path_loss_exponent, shadowing_stddev, d0, pl_d0, noise_floor, s, white_gausian_noise):
        self.path_loss_exponent = path_loss_exponent
        self.shadowing_stddev = shadowing_stddev
        self.d0 = d0
        self.pl_d0 = pl_d0
        self.noise_floor_pn = noise_floor
        self.s = s
        self.white_gausian_noise = white_gausian_noise

        self.noise_floor = None
        self.output_power_var = None
        self.link_gain = None

    def setup(self, topology, seed):
        rnd = Random(seed)

        self._check_topology(topology)

        self.noise_floor = np.zeros(len(topology.nodes))
        self.output_power_var = np.zeros(len(topology.nodes))
        self.link_gain = np.zeros((len(topology.nodes), len(topology.nodes)))

        self._obtain_radio_pt_pn(rnd, topology)

        self._obtain_link_gain(rnd, topology)

    def _check_topology(self, topology):
        for (i, ni) in enumerate(topology.nodes):
            for (j, nj) in enumerate(islice(topology.nodes, i+1, None), start=i+1):

                distance = euclidean(ni, nj)
                if distance < self.d0:
                    raise RuntimeError("The distance ({}) between any two nodes ({}={}, {}={}) must be at least d0 ({})".format(distance, i, ni, j, nj, self.d0))

    def _obtain_radio_pt_pn(self, rnd, topology):

        t = np.zeros((2, 2))

        if self.s[0,0] == 0 and self.s[1,1] == 0:
            return

        elif self.s[0,0] == 0 and self.s[1,1] != 0:
            raise RuntimeError("Symmetric links require both, S11 and S22 to be 0, not only S11.")

        else:
            if self.s[0,1] != self.s[1,0]:
                raise RuntimeError("S12 and S21 must have the same value.")

            if abs(self.s[0,1]) > pow(self.s[0,0] * self.s[1,1], 0.5):
                raise RuntimeError("S12 (and S21) must be less than sqrt(S11xS22).")

            t[0,0] = pow(self.s[0,0], 0.5)
            t[0,1] = self.s[0,1] / pow(self.s[0,0], 0.5)
            t[1,0] = 0.0
            t[1,1] = pow((self.s[0,0] * self.s[1,1] - pow(self.s[0,1], 2)) / self.s[0,0], 0.5)

        
        for (i, ni) in enumerate(topology.nodes):
            rnd1 = rnd.nextGaussian()
            rnd2 = rnd.nextGaussian()

            self.noise_floor[i] = self.noise_floor_pn + t[0,0] * rnd1
            self.output_power_var[i] = t[0,1] * rnd1 + t[1,1] * rnd2

    def _obtain_link_gain(self, rnd, topology):
        for (i, ni) in enumerate(topology.nodes):
            for (j, nj) in enumerate(islice(topology.nodes, i+1, None), start=i+1):
                rnd1 = rnd.nextGaussian()

                distance = euclidean(ni, nj)

                pathloss = -self.pl_d0 - 10.0 * self.path_loss_exponent * log10(distance / self.d0) + rnd1 * self.shadowing_stddev

                self.link_gain[i,j] = self.output_power_var[i] + pathloss
                self.link_gain[j,i] = self.output_power_var[j] + pathloss



class LowAsymmetry(CommunicationModel):
    def __init__(self):
        super(LowAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.matrix([[0.9, -0.7],[-0.7, 1.2]]),
            white_gausian_noise=4.0
        )

class HighAsymmetry(CommunicationModel):
    def __init__(self):
        super(LowAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.matrix([[3.7, -3.3],[-3.3, 6.0]]),
            white_gausian_noise=4.0
        )

class NoAsymmetry(CommunicationModel):
    def __init__(self):
        super(LowAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.matrix([[0.0, 0.0],[0.0, 0.0]]),
            white_gausian_noise=4.0
        )

MODEL_NAME_MAPPING = {
    "low-asymmetry": LowAsymmetry,
    "high-asymmetry": HighAsymmetry,
    "no-asymmetry": NoAsymmetry,
}


def models():
    """A list of the names of the available communication models."""
    return [cls for cls in CommunicationModel.__subclasses__()]

def eval_input(source):
    if source in MODEL_NAME_MAPPING:
        return MODEL_NAME_MAPPING[source]

    result = restricted_eval(source, models())

    if isinstance(result, CommunicationModel):
        return result
    else:
        raise RuntimeError("The source ({}) is not valid.".format(source))
