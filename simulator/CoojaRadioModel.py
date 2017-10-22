
from data.restricted_eval import restricted_eval

class CoojaRadioModel(object):
    def __init__(self):
        pass

    def __str__(self):
        return type(self).__name__ + "()"

class UDGMRadioModel(CoojaRadioModel):
    def __init__(self, tx_range, inter_range, tx_success, rx_success):
        super(UDGMRadioModel, self).__init__()
        self.tx_range = tx_range
        self.inter_range = inter_range
        self.tx_success = tx_success
        self.rx_success = rx_success

    def cooja_csc(self):
        return """org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>{}</transmitting_range>
      <interference_range>{}</interference_range>
      <success_ratio_tx>{}</success_ratio_tx>
      <success_ratio_rx>{}</success_ratio_rx>""".format(self.tx_range, self.inter_range, self.tx_success, self.rx_success)

    def __str__(self):
        attrs = ("tx_range", "inter_range", "tx_success", "rx_success")
        attr_str = ",".join("{}={}".format(attr, getattr(self, attr)) for attr in attrs)

        return "{}({})".format(type(self).__name__, attr_str)

def models():
    """A list of the names of the available radio models."""
    return [subcls for subcls in CoojaRadioModel.__subclasses__()]  # pylint: disable=no-member

def eval_input(source):
    result = restricted_eval(source, models())

    if isinstance(result, CoojaRadioModel):
        return result
    else:
        raise RuntimeError("The radio model ({}) is not valid.".format(source))

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
