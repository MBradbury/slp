

class MSP430Node(object):
    def node_interface_configs(self, **kwargs):
        return """
      <interface_config>
        org.contikios.cooja.mspmote.interfaces.MspClock
        <deviation>1.0</deviation>
      </interface_config>
      <interface_config>
        org.contikios.cooja.mspmote.interfaces.MspMoteID
        <id>{nid}</id>
      </interface_config>""".format(**kwargs)

class MicaZNode(object):
    def node_interface_configs(self, **kwargs):
        return """
      <interface_config>
        org.contikios.cooja.avrmote.interfaces.MicaZID
        <id>{nid}</id>
      </interface_config>
      <interface_config>
        org.contikios.cooja.avrmote.interfaces.MicaClock
        <deviation>1.0</deviation>
      </interface_config>""".format(**kwargs)

class CoojaPlatform(object):
    def __init__(self):
        pass

    def __str__(self):
        return type(self).__name__

    def __eq__(self, other):
        if self is other:
            return True

        return str(self) == str(other)

class Sky(CoojaPlatform, MSP430Node):
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

class MicaZ(CoojaPlatform, MicaZNode):
    def __init__(self):
        super(MicaZ, self).__init__()

    def cooja_csc(self):
        return """org.contikios.cooja.avrmote.MicaZMoteType
      <identifier>{platform}</identifier>
      <description>A node type of {platform}</description>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.avrmote.interfaces.MicaZID</moteinterface>
      <moteinterface>org.contikios.cooja.avrmote.interfaces.MicaZLED</moteinterface>
      <moteinterface>org.contikios.cooja.avrmote.interfaces.MicaZRadio</moteinterface>
      <moteinterface>org.contikios.cooja.avrmote.interfaces.MicaClock</moteinterface>
      <moteinterface>org.contikios.cooja.avrmote.interfaces.MicaSerial</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>""".format(platform=self.platform())

    def platform(self):
        return "micaz"

class Z1(CoojaPlatform, MSP430Node):
    def __init__(self):
        super(Z1, self).__init__()

    def cooja_csc(self):
        return """org.contikios.cooja.mspmote.Z1MoteType
      <identifier>{platform}</identifier>
      <description>A node type of {platform}</description>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.RimeAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspClock</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspButton</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.Msp802154Radio</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspDefaultSerial</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspLED</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspDebugOutput</moteinterface>""".format(platform=self.platform())

    def platform(self):
        return "z1"

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
