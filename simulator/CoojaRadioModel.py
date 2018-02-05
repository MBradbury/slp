
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
    def __init__(self):
        super().__init__()
        raise NotImplementedError("There are loads of parameters to this...")

    def cooja_csc(self):
        return "org.contikios.mrm.MRM"


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
