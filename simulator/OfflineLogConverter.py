from __future__ import print_function, division

from datetime import datetime
import re

from data.restricted_eval import restricted_eval

class OfflineLogConverter(object):
    def __init__(self, log_file):
        self._log_file = log_file

class Null(OfflineLogConverter):
    """Dummy converter that just provides iteration of the log without changes."""
    def __init__(self, log_file):
        super(Null, self).__init__(log_file)

    def __iter__(self):
        return iter(self._log_file)

class FlockLab(OfflineLogConverter):
    def __init__(self, log_file):
        super(FlockLab, self).__init__(log_file)

        self.processed_lines = []

        for line in self._log_file:
            if line.startswith('#'):
                continue
            if line == "\0\n":
                continue

            timestamp, observer_id, node_id, direction, output = line.split(",", 4)

            timestamp = float(timestamp)

            node_time = datetime.fromtimestamp(timestamp)

            self.processed_lines.append((node_time, output))

        self.processed_lines.sort(key=lambda x: x[0])

        self.processed_lines = [

            "{}|{}".format(node_time.strftime("%Y/%m/%d %H:%M:%S.%f"), output)

            for (node_time, output)
            in self.processed_lines
        ]

    def __iter__(self):
        return iter(self.processed_lines)


    # First line is a comment that begins with a #
    # Each line is comma separated with "timestamp,observer_id,node_id,direction,output"

    # Logs are grouped together by node id
    # The time will reset to earlier when the serial output for a new node is encountered

class Avrora(OfflineLogConverter):

    results_start = "------------------------------------------------------------------------------"
    results_end = "=============================================================================="

    RESULT_LINE_RE = re.compile(r'\s*(\d+)\s*(\d+:\d+:\d+\.\d+)\s*(.+)\s*')
    TX_LINE_RE = re.compile(r'---->\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')
    RX_LINE_RE = re.compile(r'<====\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')

    def __init__(self, log_file):
        super(Avrora, self).__init__(log_file)
        self._log_file_iter = iter(log_file)

        self.started = False
        self.ended = False

        self.average_tx_length = 0
        self.average_rx_length = 0

        self.average_tx_count = 0
        self.average_rx_count = 0

    @staticmethod
    def _incremental_ave(curr, item, count):
        return curr + (item - curr) / (count + 1), count + 1

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            line = next(self._log_file_iter)

            if not started and line.startswith(self.results_start):
                started = True
                #print("started")
                continue

            if not started:
                continue

            if line.startswith(self.results_end):
                ended = True
                #print("ended")
                continue

            if started and not ended:
                match = self.RESULT_LINE_RE.match(line)

                node = int(match.group(1))
                node_time = datetime.strptime(match.group(2)[:-3], "%H:%M:%S.%f")

                log = match.group(3)

                if log.startswith("---->"):
                    tx_match = self.TX_LINE_RE.match(log)
                    data = tx_match.group(1)
                    time_length_ms = float(tx_match.group(2))

                    self.average_tx_length, self.average_tx_count = self._incremental_ave(self.average_tx_length, time_length_ms, self.average_tx_count)

                elif log.startswith("<===="):
                    rx_match = self.RX_LINE_RE.match(log)
                    data = rx_match.group(1)
                    time_length_ms = float(rx_match.group(2))

                    self.average_rx_length, self.average_rx_count = self._incremental_ave(self.average_rx_length, time_length_ms, self.average_rx_count)

                else:
                    dtime_str = node_time.strftime("%Y/%m/%d %H:%M:%S.%f")

                    # Then its one of our debug log messages
                    return "{}|{}".format(dtime_str, log)

    # Python 2 support
    def next(self):
        return self.__next__()


class Indriya(OfflineLogConverter):
    def __init__(self, log_file):
        super(Indriya, self).__init__(log_file)


def models():
    """A list of the available models."""
    return [f for f in OfflineLogConverter.__subclasses__()]  # pylint: disable=no-member

def names():
    return [f.__name__ for f in models()]

def create_specific(name, *args, **kwargs):
    confs = [cls for cls in models() if cls.__name__ == name]

    if len(confs) == 0:
        raise RuntimeError("No offline log converters were found using the name {}, args {}".format(name, args))

    if len(confs) > 1:
        raise RuntimeError("There are multiple offline log converters that have the name {}, not sure which one to choose".format(name))

    return confs[0](*args, **kwargs)
