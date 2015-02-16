from collections import OrderedDict

import math

class PeriodModel(object):
    def __init__(self, times):
        self.period_times = times

        self._validate_times()

    def _validate_times(self):
        pass

    def build_arguments(self):
        build_arguments = {}

        def to_tinyos_format(time):
            return int(time * 1000)

        periods = [
            "{{{}U, {}U}}".format(to_tinyos_format(end), to_tinyos_format(period))
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

        build_arguments["PERIOD_TIMES_MS"] = "{ " + ", ".join(periods) + " }"
        build_arguments["PERIOD_ELSE_TIME_MS"] = "{}U".format(end_period)

        return build_arguments

class FixedPeriodModel(PeriodModel):
    def __init__(self, period):

        times = OrderedDict()
        times[(0, float('inf'))] = period

        super(FixedPeriodModel, self).__init__(times)

class FactoringPeriodModel(PeriodModel):
    def __init__(self, starting_period, max_period, duration, factor):

        times = OrderedDict()

        period = float(starting_period)
        current_time = 0.0

        while period <= max_period:

            end_time = current_time + duration if period * factor <= max_period else float('inf')

            times[(current_time, end_time)] = period

            current_time = end_time
            period *= factor

        super(FactoringPeriodModel, self).__init__(times)

def models():
    """A list of the names of the available period models."""
    return [cls for cls in PeriodModel.__subclasses__()]
