
class CoojaPlatform(object):
    def __init__(self):
        pass

    def __str__(self):
        return type(self).__name__

    def __eq__(self, other):
        if self is other:
            return True

        return str(self) == str(other)

class Sky(CoojaPlatform):
    def __init__(self):
        super(Sky, self).__init__()

    def cooja_csc(self):
        return """org.contikios.cooja.mspmote.SkyMoteType
      <identifier>{platform}</identifier>
      <description>A node type of {platform}</description>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.RimeAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspClock</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyButton</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyFlash</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyCoffeeFilesystem</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.Msp802154Radio</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspSerial</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyLED</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspDebugOutput</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyTemperature</moteinterface>""".format(platform=self.platform())

    def platform(self):
        return "telosb"

def models():
    """A list of the names of the available radio models."""
    return [subcls for subcls in CoojaPlatform.__subclasses__()]  # pylint: disable=no-member

def eval_input(source):
    options = [x for x in models() if x.__name__ == source]
    if len(options) == 1:
        return options[0]()
    else:
        raise RuntimeError("The radio model ({}) is not valid.".format(source))

def available_models():
    return [x.__name__ for x in models()]
