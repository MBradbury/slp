
import binascii
from datetime import datetime
import glob
import os.path
import re
import traceback

import numpy as np
import pandas

def _sanitise_string(input_string):
    if len(input_string) > 255:
        input_string = input_string[:255] + "..."

    return input_string

class OfflineLogConverter(object):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class LineLogConverter(object):
    def __init__(self, log_path):
        super().__init__()

        self.log_path = log_path
        self.processed_lines = None

        with open(log_path, 'r', encoding="ascii", errors="ignore") as log_file:
            self._process_file(log_file)

    def _process_file(self, log_file):
        raise NotImplementedError()

    def __iter__(self):
        return iter(self.processed_lines)

class Null(OfflineLogConverter):
    """Dummy converter that just provides iteration of the log without changes."""
    def __init__(self, log_path):
        super().__init__()

        self.log_path = log_path
        self._log_file = open(log_path, 'r')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._log_file.close()

    def __iter__(self):
        return iter(self._log_file)

class FlockLab(OfflineLogConverter, LineLogConverter):
    def __init__(self, log_path):
        super().__init__(log_path)

    def _process_line(self, line):
        timestamp, observer_id, node_id, direction, output = line.split(",", 4)

        timestamp = float(timestamp)

        node_time = datetime.fromtimestamp(timestamp)

        # Remove newline from output
        output = output.strip()

        return [(node_time, output)]

    def _process_gpio_line(self, line):
        timestamp, observer_id, node_id, name, value = line.split(",", 4)

        timestamp = float(timestamp)

        node_time = datetime.fromtimestamp(timestamp)

        if not name.startswith('LED'):
            raise ValueError(f"Bad name {name}, expected LED")

        led_num = int(name[len("LED"):]) - 1
        led_value = "on" if value.strip() == "1" else "off"

        # Remove newline from output
        output = f"LedsC:D:{node_id}:None:{led_num},{led_value}"

        return (node_time, output)

    def _process_file(self, log_file):

        self.processed_lines = []

        for line in log_file:
            if line.startswith('#'):
                continue
            if line.endswith("\0\n"):
                continue

            try:
                output = self._process_line(line)
            except ValueError as ex:
                print("Failed to parse the line:", _sanitise_string(line))
                traceback.print_exc()
                continue

            if output:
                self.processed_lines.extend(output)

        # Also need to process gpio tracing
        gpiotracing_path = os.path.join(os.path.dirname(log_file.name), "gpiotracing.csv")
        with open(gpiotracing_path, "r") as gpiotracing_file:
            for line in gpiotracing_file:
                if line.startswith('#'):
                    continue
                if line.endswith("\0\n"):
                    continue

                try:
                    output = self._process_gpio_line(line)
                except ValueError as ex:
                    print("Failed to parse the line:", _sanitise_string(line))
                    traceback.print_exc()
                    continue

                self.processed_lines.append(output)

        # MUST sort output here, as flocklab output is grouped by node ids
        self.processed_lines.sort(key=lambda x: x[0])


    # First line is a comment that begins with a #
    # Each line is comma separated with "timestamp,observer_id,node_id,direction,output"

    # Logs are grouped together by node id
    # The time will reset to earlier when the serial output for a new node is encountered

class HexFlockLab(FlockLab, OfflineLogConverter):
    # Assumes that log lines for the same node are adjacent
    def __init__(self, log_path):

        self._buffer_timestamp = None
        self._buffer = ""

        super().__init__(log_path)

    def _process_line(self, line):
        timestamp, observer_id, node_id, direction, output = line.split(",", 4)

        timestamp = float(timestamp)

        node_time = datetime.fromtimestamp(timestamp)

        # Remove newline from output
        output = output.strip()
        output = output[len("00ffff00001c0064"):]

        # Get rid of NUL padding bytes
        while output.endswith("00"):
            output = output[:-len("00")]

        output = binascii.unhexlify(output).decode("utf-8")

        self._buffer += output

        print("CURRENT BUFF '", self._buffer, "'")

        result = []

        newline_idx = self._buffer.find('\n')
        while newline_idx != -1:

            out = self._buffer[:newline_idx]
            self._buffer = self._buffer[newline_idx+1:]

            prev_timestamp = self._buffer_timestamp if self._buffer_timestamp else node_time

            result.append((prev_timestamp, out))

            newline_idx = self._buffer.find('\n')

        self._buffer_timestamp = node_time if self._buffer else None

        return result


class FitIotLab(OfflineLogConverter, LineLogConverter):
    def __init__(self, log_path):
        super().__init__(log_path)

    def _process_file(self, log_file):
        self._check_nul_byte_log_file(log_file)

        usecols = ["globaltime", "metric", "localtime", "kind", "node", "data"]

        df = pandas.read_csv(log_file,
            sep="[;:]",
            header=None,
            names=("globaltime", "testbed node", "metric", "kind", "node", "localtime", "data"),
            usecols=usecols,
            dtype={
                "globaltime": np.float_,
                #"metric": "category",
                #"localtime": np.uint32,
                #"node": np.uint16,
            },
            engine="python",
            nrows=1000000,
        )

        # Remove missing data
        df.dropna(subset=("node", "localtime"), how="any", inplace=True)

        # Coerce types
        df["globaltime"] = pandas.to_datetime(df["globaltime"], unit='s')
        #df["localtime"] = df["localtime"].astype(np.uint32)
        df["node"] = df["node"].astype(np.uint16)

        # mergesort to be stable
        #df.sort_values("globaltime", kind="mergesort", inplace=True)

        # Change order
        df = df[usecols]

        #print(df[df["node"] == 153])

        self.processed_lines = df.itertuples(index=False)

    def _check_nul_byte_log_file(self, log_file):
        firstn = log_file.read(1024)

        # Reset file back to the beginning
        log_file.seek(0)

        ratio = sum(x == 0 for x in firstn) / len(firstn)

        if ratio >= 0.5:
            raise RuntimeError("File ({}) consists of NUL bytes ({}), skipping it".format(log_file.name, ratio))

class Avrora(OfflineLogConverter):

    results_start = "------------------------------------------------------------------------------"
    results_end = "=============================================================================="

    RESULT_LINE_RE = re.compile(r'\s*(\d+)\s*(\d+:\d+:\d+\.\d+)\s*(.+)\s*')
    TX_LINE_RE = re.compile(r'---->\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')
    RX_LINE_RE = re.compile(r'<====\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')

    def __init__(self, log_path):
        super().__init__()

        self._log_file = open(log_path, 'r')
        self._log_file_iter = iter(self._log_file)

        self.started = False
        self.ended = False

        self.average_tx_length = 0
        self.average_rx_length = 0

        self.average_tx_count = 0
        self.average_rx_count = 0

    @staticmethod
    def _incremental_ave(curr, item, count):
        return curr + (item - curr) / (count + 1), count + 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._log_file.close()

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            line = next(self._log_file_iter)

            if not self.started and line.startswith(self.results_start):
                self.started = True
                #print("started")
                continue

            if not self.started:
                continue

            if line.startswith(self.results_end):
                self.ended = True
                #print("ended")
                continue

            if self.started and not self.ended:
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

class SerialMessageLogConverter(object):
    AM_EVENT_OCCURRED_MSG = 48
    AM_ERROR_OCCURRED_MSG = 49
    AM_METRIC_RECEIVE_MSG = 50
    AM_METRIC_BCAST_MSG = 51
    AM_METRIC_DELIVER_MSG = 52
    AM_ATTACKER_RECEIVE_MSG = 53
    AM_METRIC_NODE_CHANGE_MSG = 54
    AM_METRIC_NODE_TYPE_ADD_MSG = 55
    AM_METRIC_MESSAGE_TYPE_ADD_MSG = 56
    AM_METRIC_NODE_SLOT_CHANGE_MSG = 57
    AM_METRIC_PARENT_CHANGE_MSG = 58
    AM_METRIC_START_PERIOD_MSG = 59
    AM_METRIC_FAULT_POINT_TYPE_ADD_MSG = 60
    AM_METRIC_FAULT_POINT_MSG = 61

    message_types_to_channels = {
        AM_METRIC_RECEIVE_MSG:          ("M-CR",    ("message_type", "proximate_source", "ultimate_source", "sequence_number", "distance")),
        AM_METRIC_BCAST_MSG:            ("M-CB",    ("message_type", "status", "sequence_number")),
        AM_METRIC_DELIVER_MSG:          ("M-CD",    ("message_type", "proximate_source", "ultimate_source_poss_bottom", "sequence_number")),
        AM_ATTACKER_RECEIVE_MSG:        ("A-R",     ("message_type", "proximate_source", "ultimate_source_poss_bottom", "sequence_number")),
        AM_METRIC_NODE_CHANGE_MSG:      ("M-NC",    ("old_node_type", "new_node_type")),
        AM_ERROR_OCCURRED_MSG:          ("stderr",  ("error_code",)),
        AM_EVENT_OCCURRED_MSG:          ("stdout",  ("event_code",)),
        AM_METRIC_NODE_TYPE_ADD_MSG:    ("M-NTA",   ("node_type_id", "node_type_name")),
        AM_METRIC_MESSAGE_TYPE_ADD_MSG: ("M-MTA",   ("message_type_id", "message_type_name")),
    }

    def catter_header(self, row, d_or_e, channel):
        return "{}|{}:{}:{}:{}:".format(row["date_time"], channel, d_or_e, row["node_id"], row["local_time"])

    def catter_row(self, row, channel, headers):
        return self.catter_header(row, "D", channel) + ",".join(str(row[header]) for header in headers)

    def _read_dat_file(self, path):
        try:
            reader = pandas.read_csv(path, delimiter="\t", parse_dates=True)

            # Check there is only one message type
            if len(reader["type"].unique()) != 1:
                raise RuntimeError("The type column has more than 1 value.")

            message_type = reader["type"][0]

            reader["date_time"] = reader["insert_time"].apply(lambda x: x.replace("-", "/")) + "." + reader["milli_time"].apply(lambda x: str(x % 1000).ljust(3, '0'))

            reader["milli_time"] -= reader["milli_time"][0]

            return (message_type, reader)

        except pandas.io.common.EmptyDataError:
            # Skip empty files
            return (None, None)

    def _create_combined_results(self, log_path):
        dat_file_paths = glob.glob(os.path.join(log_path, "*.dat"))

        dat_files = {
            message_type: reader
            for (message_type, reader)
            in (self._read_dat_file(path) for path in dat_file_paths)
            if message_type is not None
        }

        if len(dat_files) == 0:
            raise RuntimeError("All dat files were empty, no results present.")

        # Remove "\0" from any fields that are strings
        to_remove_nul_char = [(self.AM_METRIC_NODE_TYPE_ADD_MSG, "node_type_name"), (self.AM_METRIC_MESSAGE_TYPE_ADD_MSG, "message_type_name")]

        for (ident, name) in to_remove_nul_char:
            dat_files[ident][name] = dat_files[ident][name].apply(lambda x: x.replace("\\0", ""))

        # Find out the numeric to name mappings for message types
        node_types = (
            dat_files[self.AM_METRIC_NODE_TYPE_ADD_MSG][["node_type_id", "node_type_name"]]
                .drop_duplicates()
                .set_index("node_type_id")
                .to_dict()["node_type_name"]
        )

        # Find out the numeric to name mappings for message types
        message_types = (
            dat_files[self.AM_METRIC_MESSAGE_TYPE_ADD_MSG][["message_type_id", "message_type_name"]]
                .drop_duplicates()
                .set_index("message_type_id")
                .to_dict()["message_type_name"]
        )

        # Convert any node type ids to node type names
        to_convert_node_type = [(self.AM_METRIC_NODE_CHANGE_MSG, "old_node_type"), (self.AM_METRIC_NODE_CHANGE_MSG, "new_node_type")]

        for (ident, name) in to_convert_node_type:
            dat_files[ident][name] = dat_files[ident][name].apply(lambda x: node_types.get(x, "<unknown>"))

        dfs = []

        for (message_type, dat_file) in dat_files.items():
            channel, headers = self.message_types_to_channels[message_type]

            # Convert numeric message type to string
            if "message_type" in dat_file:
                dat_file["message_type"] = dat_file["message_type"].apply(lambda x: message_types[x])

            # Get the df we want to output
            df = pandas.DataFrame({
                "line": dat_file.apply(self.catter_row, axis=1, args=(channel, headers)),
                "time": dat_file["milli_time"]
            })

            dfs.append(df)

        cdf = pandas.concat(dfs).sort_values(by="time")

        del cdf["time"]

        return cdf            


class Indriya(OfflineLogConverter, SerialMessageLogConverter):
    def __init__(self, log_path):
        super().__init__()

        self.cdf = self._create_combined_results(log_path)
        
    def __iter__(self):
        return iter(self.cdf["line"])


def models():
    """A list of the available models."""
    return OfflineLogConverter.__subclasses__()  # pylint: disable=no-member

def names():
    return [f.__name__.lower() for f in models()]

def create_specific(name, *args, **kwargs):
    confs = [cls for cls in models() if cls.__name__.lower() == name.lower()]

    if len(confs) == 0:
        raise RuntimeError("No offline log converters were found using the name {}, args {}".format(name, args))

    if len(confs) > 1:
        raise RuntimeError("There are multiple offline log converters that have the name {}, not sure which one to choose".format(name))

    return confs[0](*args, **kwargs)
