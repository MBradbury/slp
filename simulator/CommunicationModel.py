from __future__ import division

from math import log10, sqrt
from itertools import islice

import numpy as np

class CommunicationModel(object):
    def __init__(self):
        self.noise_floor = None
        self.link_gain = None
        self.white_gausian_noise = None

    def setup(self, sim):
        raise NotImplementedError()

class LinkLayerCommunicationModel(CommunicationModel):
    def __init__(self, path_loss_exponent, shadowing_stddev, d0, pl_d0, noise_floor, s, white_gausian_noise):
        super(LinkLayerCommunicationModel, self).__init__()

        self.path_loss_exponent = path_loss_exponent
        self.shadowing_stddev = shadowing_stddev
        self.d0 = d0
        self.pl_d0 = pl_d0
        self.noise_floor_pn = noise_floor
        self.s = s
        self.white_gausian_noise = round(white_gausian_noise, 2)

        self.output_power_var = None

    def setup(self, sim):
        topology = sim.metrics.configuration.topology
        seed = sim.seed
        self._setup(topology, seed)

    def _setup(self, topology, seed):
        # Need to use the same java prng to maintain backwards compatibility
        # with existing results
        # TODO: When creating results from scratch, switch to python's rng as it is much better
        from java_random import JavaRandom as Random

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

                distance = topology.coord_distance_meters(ni, nj)
                if distance < self.d0:
                    raise RuntimeError("The distance ({}) between any two nodes ({}={}, {}={}) must be at least d0 ({})".format(
                        distance, i, ni, j, nj, self.d0))

    def _obtain_radio_pt_pn(self, rnd, topology):

        s = self.s
        t = np.zeros((2, 2))

        if s[0,0] == 0 and s[1,1] == 0:
            pass

        elif s[0,0] == 0 and s[1,1] != 0:
            raise RuntimeError("Symmetric links require both, S11 and S22 to be 0, not only S11.")

        else:
            if s[0,1] != s[1,0]:
                raise RuntimeError("S12 and S21 must have the same value.")

            if abs(s[0,1]) > sqrt(s[0,0] * s[1,1]):
                raise RuntimeError("S12 (and S21) must be less than sqrt(S11xS22).")

            t00 = sqrt(s[0,0])

            t[0,0] = t00
            t[0,1] = s[0,1] / t00
            t[1,0] = 0.0
            t[1,1] = sqrt((s[0,0] * s[1,1] - s[0,1] * s[0,1]) / s[0,0])

        
        for (i, ni) in enumerate(topology.nodes):
            rnd1 = rnd.nextGaussian()
            rnd2 = rnd.nextGaussian()

            # The results here need to be rounded to 2 d.p. to make sure
            # that the results of the simulation match the java results.

            self.noise_floor[i] = round(self.noise_floor_pn + t[0,0] * rnd1, 2)
            self.output_power_var[i] = t[0,1] * rnd1 + t[1,1] * rnd2

    def _obtain_link_gain(self, rnd, topology):
        for (i, ni) in enumerate(topology.nodes):
            for (j, nj) in enumerate(islice(topology.nodes, i+1, None), start=i+1):
                rnd1 = rnd.nextGaussian()

                distance = topology.coord_distance_meters(ni, nj)

                pathloss = -self.pl_d0 - 10.0 * self.path_loss_exponent * log10(distance / self.d0) + rnd1 * self.shadowing_stddev

                # The results here need to be rounded to 2 d.p. to make sure
                # that the results of the simulation match the java results.

                self.link_gain[i,j] = round(self.output_power_var[i] + pathloss, 2)
                self.link_gain[j,i] = round(self.output_power_var[j] + pathloss, 2)



class IdealCommunicationModel(CommunicationModel):
    def __init__(self, connection_strength, noise_floor_pn, white_gausian_noise):
        super(IdealCommunicationModel, self).__init__()

        self.connection_strength = connection_strength
        self.noise_floor_pn = noise_floor_pn
        self.white_gausian_noise = white_gausian_noise

    def setup(self, sim):
        topology = sim.metrics.configuration.topology

        self.noise_floor = np.zeros(len(topology.nodes))
        self.link_gain = np.zeros((len(topology.nodes), len(topology.nodes)))

        self._obtain_link_gain(topology, sim.wireless_range)
        self._obtain_noise_floor(topology)

    def _obtain_link_gain(self, topology, wireless_range):
        for (i, ni) in enumerate(topology.nodes):
            for (j, nj) in enumerate(islice(topology.nodes, i+1, None), start=i+1):
                if topology.coord_distance_meters(ni, nj) <= wireless_range:
                    self.link_gain[i,j] = self.connection_strength
                    self.link_gain[j,i] = self.connection_strength
                else:
                    # Use NaNs to signal that there is no link between these two nodes
                    self.link_gain[i,j] = float('NaN')
                    self.link_gain[j,i] = float('NaN')

    def _obtain_noise_floor(self, topology):
        for (i, ni) in enumerate(topology.nodes):
            self.noise_floor[i] = self.noise_floor_pn



class LowAsymmetry(LinkLayerCommunicationModel):
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

class HighAsymmetry(LinkLayerCommunicationModel):
    def __init__(self):
        super(HighAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.matrix([[3.7, -3.3],[-3.3, 6.0]]),
            white_gausian_noise=4.0
        )

class NoAsymmetry(LinkLayerCommunicationModel):
    def __init__(self):
        super(NoAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.matrix([[0.0, 0.0],[0.0, 0.0]]),
            white_gausian_noise=4.0
        )

class Ideal(IdealCommunicationModel):
    """Perfect receive signal strength for all nodes within range."""
    def __init__(self):
        super(Ideal, self).__init__(
            connection_strength=-55,
            noise_floor_pn=-105.0,
            white_gausian_noise=4.0
        )

# Backwards compatibility:
# These are the mappings of the old names used to refer to the models
MODEL_NAME_MAPPING = {
    "low-asymmetry": LowAsymmetry,
    "high-asymmetry": HighAsymmetry,
    "no-asymmetry": NoAsymmetry,
    "ideal": Ideal,
}

def models():
    """A list of the names of the available communication models."""
    return [subsubcls
            for subcls in CommunicationModel.__subclasses__()
            for subsubcls in subcls.__subclasses__()]

def eval_input(source):
    if source in MODEL_NAME_MAPPING:
        return MODEL_NAME_MAPPING[source]

    result = restricted_eval(source, models())

    if isinstance(result, CommunicationModel):
        return result
    else:
        raise RuntimeError("The source ({}) is not valid.".format(source))
