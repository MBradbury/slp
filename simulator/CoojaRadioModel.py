
from data.restricted_eval import restricted_eval

class CoojaRadioModel(object):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return type(self).__name__ + "()"

    def short_name(self):
        return str(self)

class UDGMRadioModel(CoojaRadioModel):
    """Unit Disk Graph Model - Distance Loss"""
    def __init__(self, tx_range, inter_range, tx_success, rx_success):
        super().__init__()
        self.tx_range = tx_range
        self.inter_range = inter_range
        self.tx_success = tx_success
        self.rx_success = rx_success

    def cooja_csc(self):
        return f"""org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>{self.tx_range}</transmitting_range>
      <interference_range>{self.inter_range}</interference_range>
      <success_ratio_tx>{self.tx_success}</success_ratio_tx>
      <success_ratio_rx>{self.rx_success}</success_ratio_rx>"""

    def _build_str(self, *, short):
        attrs = ("tx_range", "inter_range", "tx_success", "rx_success")

        if not short:
            attr_str = ",".join(f"{attr}={getattr(self, attr)}" for attr in attrs)
        else:
            attr_str = ",".join(f"{getattr(self, attr)}" for attr in attrs)

        return f"{type(self).__name__}({attr_str})"

    def __str__(self):
        return self._build_str(short=False)

    def short_name(self):
        return self._build_str(short=True)


class UDGMConstantLossRadioModel(CoojaRadioModel):
    """Unit Disk Graph Model - Constant Loss"""
    def __init__(self, tx_range, inter_range, tx_success, rx_success):
        super().__init__()
        self.tx_range = tx_range
        self.inter_range = inter_range
        self.tx_success = tx_success
        self.rx_success = rx_success

    def cooja_csc(self):
        return f"""org.contikios.cooja.radiomediums.UDGMConstantLoss
      <transmitting_range>{self.tx_range}</transmitting_range>
      <interference_range>{self.inter_range}</interference_range>
      <success_ratio_tx>{self.tx_success}</success_ratio_tx>
      <success_ratio_rx>{self.rx_success}</success_ratio_rx>"""

    def _build_str(self, *, short):
        attrs = ("tx_range", "inter_range", "tx_success", "rx_success")

        if not short:
            attr_str = ",".join(f"{attr}={getattr(self, attr)}" for attr in attrs)
        else:
            attr_str = ",".join(f"{getattr(self, attr)}" for attr in attrs)

        return f"{type(self).__name__}({attr_str})"

    def __str__(self):
        return self._build_str(short=False)

    def short_name(self):
        return self._build_str(short=True)

class DirectedGraphRadioModel(CoojaRadioModel):
    def __init__(self):
        super().__init__()

        self.edges = {}

    def add_edge(self, source, dest, signal, lqi, delay=0, ratio=1.0, channel=-1):
        if source not in self.edges:
            self.edges[source] = []

        self.edges[source].append((dest, signal, lqi, delay, ratio, channel))

    def cooja_csc(self):
        result = "org.contikios.cooja.radiomediums.DirectedGraphMedium"

        for (source, src_edges) in self.edges.items():
            for (dest, signal, lqi, delay, ratio, channel) in src_edges:
                result += f"""
      <edge>
        <source>{source}</source>
        <dest>
          org.contikios.cooja.radiomediums.DGRMDestinationRadio
          <radio>{dest}</radio>
          <ratio>{ratio}</ratio>
          <signal>{signal}</signal>
          <lqi>{lqi}</lqi>
          <delay>{delay}</delay>
          <channel>{channel}</channel>
        </dest>
      </edge>"""

        return result

# TODO: Implement a TestbedRadioModel based on DirectedGraphRadioModel and TestbedCommunicationModel

class MRMRadioModel(CoojaRadioModel):
    """Multi-path Ray-tracer medium"""

    parameter_defaults = (
        ("apply_random", "false"),
        ("snr_threshold", "6"),
        ("bg_noise_mean", "-100"),
        ("bg_noise_var", "1"),
        ("system_gain_mean", "0"),
        ("system_gain_var", "4"),
        ("frequency", "2400"),
        ("tx_power", "1.5"),
        ("tx_with_gain", "true"),
        ("rx_sensitivity", "-100"),
        ("rx_with_gain", "false"),
        ("rt_disallow_direct_path", "false"),
        ("rt_ignore_non_direct", "false"),
        ("rt_fspl_on_total_length", "true"),
        ("rt_max_rays", "1"),
        ("rt_max_refractions", "1"),
        ("rt_max_reflections", "1"),
        ("rt_max_diffractions", "0"),
        ("rt_use_scattering", "false"),
        ("rt_refrac_coefficient", "-3"),
        ("rt_reflec_coefficient", "-5"),
        ("rt_diffr_coefficient", "-10"),
        ("rt_scatt_coefficient", "-20"),
        ("obstacle_attenuation", "-3"),
        ("captureEffect", "true"),
        ("captureEffectPreambleDuration", str(1000*1000*4*0.5*8/250000)),
        ("captureEffectSignalTreshold", "3"),
    )

    def __init__(self, **kwargs):
        super().__init__()

        self.kwargs = kwargs

        # Check validity of parameter names
        names = {x[0] for x in self.parameter_defaults}

        for key in self.kwargs:
            if key not in names:
                raise RuntimeError(f"{key} is not in the allowed set of MRM parameter names")


    def cooja_csc(self):
        return "org.contikios.mrm.MRM\n" + \
            "\n".join(f"<{name} value=\"{self.kwargs.get(name, default)}\" />" for (name, default) in self.parameter_defaults) + \
            "<obstacles />"


class LogisticLossRadioModel(CoojaRadioModel):
    """Logistic Loss Radio Model"""

    parameter_defaults = (
        ("transmitting_range", "20"),
        ("success_ratio_tx", "1"),
        ("rx_sensitivity", "-100"),
        ("rssi_inflection_point", "-92"),
        ("path_loss_exponent", "3"),
        ("awgn_sigma", "3"),
        ("enable_time_variation", "false"),
        ("time_variation_min_pl_db", "-10"),
        ("time_variation_max_pl_db", "+10"),
    )

    def __init__(self, **kwargs):
        super().__init__()

        self.kwargs = kwargs

        # Check validity of parameter names
        names = {x[0] for x in self.parameter_defaults}

        for key in self.kwargs:
            if key not in names:
                raise RuntimeError(f"{key} is not in the allowed set of MRM parameter names")

    def cooja_csc(self):
        return "org.contikios.cooja.radiomediums.LogisticLoss\n" + \
            "\n".join(f"<{name}>{self.kwargs.get(name, default)}</{name}>" for (name, default) in self.parameter_defaults)



def models():
    """A list of the names of the available radio models."""
    return [subcls for subcls in CoojaRadioModel.__subclasses__()]  # pylint: disable=no-member

def eval_input(source):
    result = restricted_eval(source, models())

    if isinstance(result, CoojaRadioModel):
        return result
    else:
        raise RuntimeError(f"The radio model ({source}) is not valid.")

def available_models():
    class WildcardModelChoice(object):
        """A special available model that checks if the string provided
        matches the name of the class."""
        def __init__(self, cls):
            self.cls = cls

        def __eq__(self, value):
            return isinstance(value, self.cls)

        def __repr__(self):
            return self.cls.__name__ + "(...)"

    return [WildcardModelChoice(x) for x in models()]
