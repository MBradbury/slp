from __future__ import print_function, division

import Attacker

from data.restricted_eval import restricted_eval

class AttackerConfiguration(object):
    def __init__(self, attackers):
        self.attackers = attackers

    def setup(self, sim):
        # Setup each attacker model, giving them their own unique identifier
        for (i, attacker) in enumerate(self.attackers):

            attacker.setup(sim, ident=i)

            sim.add_attacker(attacker)

    def __str__(self):
        return "{}({})".format(type(self).__name__, ",".join(str(attacker) for attacker in self.attackers))

    def short_str(self):
        return "{}({})".format(type(self).__name__, ",".join(attacker.short_str() for attacker in self.attackers))

class SingleAttacker(AttackerConfiguration):
    """
    Encapsulate the notion of a single attacker.
    This class allows an attacker configuration to act as an attacker model in a backwards compatible way.
    """
    def __init__(self, attacker):
        super(SingleAttacker, self).__init__([attacker])

    def __str__(self):
        return str(self.attackers[0])

    def short_str(self):
        return self.attackers[0].short_str()

class MultipleAttackers(AttackerConfiguration):
    """
    Allows specifying multiple arbitrary attackers on the command line.

    For example a command might look like: -am "MultipleAttackers(SeqNosReactiveAttacker(start_location='top_right'),SeqNosReactiveAttacker())"
    """
    def __init__(self, *args):
        super(MultipleAttackers, self).__init__(args)


def models():
    """A list of the the available attacker configurations."""
    # Do not include SingleAttacker as an available model, just get users to pass
    # an attacker model directly instead.
    return [cls for cls in AttackerConfiguration.__subclasses__() if cls != SingleAttacker] # pylint: disable=no-member

def eval_input(source):
    # Need to allow restricted_eval access to the attacker classes
    all_models = models() + Attacker.models()

    result = restricted_eval(source, all_models)

    # If we have just been passed a single attacker, then make it an attacker configuration
    if isinstance(result, Attacker.Attacker):
        result = SingleAttacker(result)

    if result in all_models:
        raise RuntimeError("The source ({}) is not valid. (Did you forget the brackets after the name?)".format(source))

    if not isinstance(result, AttackerConfiguration):
        raise RuntimeError("The source ({}) is not a valid instance of an Attacker.".format(source))

    return result

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

    class AttackerWildcardModelChoice(object):
        def __init__(self, cls):
            self.cls = cls

        def __eq__(self, value):
            return isinstance(value, SingleAttacker) and len(value.attackers) == 1 and isinstance(value.attackers[0], self.cls)

        def __repr__(self):
            return self.cls.__name__ + "(...)"

    return [WildcardModelChoice(x) for x in models()] + [AttackerWildcardModelChoice(x) for x in Attacker.models()]
