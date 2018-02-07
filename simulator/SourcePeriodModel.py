
from collections import OrderedDict
import math
import numbers

from data.memoize import memoize
from data.restricted_eval import restricted_eval


class PeriodModel(object):
    def __init__(self, times):
        self.period_times = times

        self._validate_times()

    def _validate_times(self):
        # TODO: Check that the times do not overlap
        pass

    def fastest(self):
        """Returns the smallest period possible with this model"""
        raise NotImplementedError()

    def slowest(self):
        """Returns the largest period possible with this model"""
        raise NotImplementedError()

    def build_arguments(self):
        build_arguments = {}

        def to_tinyos_format(time):
            """Return the time in milliseconds"""
            return f"UINT32_C({int(time * 1000)})"

        periods = [
            f"{{{to_tinyos_format(end)}, {to_tinyos_format(period)}}}"
            for ((start, end), period)
            in self.period_times.items()
            if not math.isinf(end)
        ]

        end_period = [
            to_tinyos_format(period)
            for ((start, end), period)
            in self.period_times.items()
            if math.isinf(end)
        ][0]

        build_arguments["PERIOD_TIMES_LEN"] = len(periods)
        build_arguments["PERIOD_TIMES_MS"] = "{ " + ", ".join(periods) + " }"
        build_arguments["PERIOD_ELSE_TIME_MS"] = end_period

        return build_arguments

    def simple_str(self):
        """Return the simplest representation of this model."""
        return repr(self)


class FixedPeriodModel(PeriodModel):
    """The sources broadcast at a fixed rate forever"""
    
    def __init__(self, period):

        self.period = float(period)

        times = OrderedDict()
        times[(0, float('inf'))] = self.period

        super(FixedPeriodModel, self).__init__(times)

    def fastest(self):
        return self.period

    def slowest(self):
        return self.period

    def simple_str(self):
        """Overloaded this method as a number also represents a fixed source period model."""
        return str(self.period)

    def __repr__(self):
        return f"FixedPeriodModel(period={self.period})"

    def __float__(self):
        return self.period

class FactoringPeriodModel(PeriodModel):
    def __init__(self, starting_period, max_period, duration, factor):

        self.starting_period = float(starting_period)
        self.max_period = float(max_period)
        self.duration = float(duration)
        self.factor = float(factor)

        if self.factor <= 1:
            raise RuntimeError("The factor ({}) must be greater than 1".format(self.factor))

        times = OrderedDict()

        period = float(starting_period)
        current_time = 0.0

        while period <= max_period:

            end_time = current_time + duration if period * factor <= max_period else float('inf')

            times[(current_time, end_time)] = period

            current_time = end_time
            period *= factor

        self.ending_period = period

        super(FactoringPeriodModel, self).__init__(times)

    def fastest(self):
        return self.starting_period

    def slowest(self):
        return self.ending_period

    def __repr__(self):
        return "FactoringPeriodModel(starting_period={}, max_period={}, duration={}, factor={})".format(
            self.starting_period, self.max_period, self.duration, self.factor)


def models():
    """A list of the names of the available period models."""
    return PeriodModel.__subclasses__()  # pylint: disable=no-member


@memoize
def create_specific(source):
    """Creates a source period model from the :source: string"""
    result = restricted_eval(source, models())

    if isinstance(result, numbers.Number):
        return FixedPeriodModel(result)
    elif isinstance(result, PeriodModel):
        return result
    else:
        raise RuntimeError(f"The source ({source}) is not valid.")


# eval_input must be a function so it can be used as a type parameter for the arguments
def eval_input(source):
    """Creates a source period model from the :source: string"""
    return create_specific(source)
