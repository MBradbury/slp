
import datetime
import timeit

class Progress(object):
    def __init__(self, description):
        self.start_time = None
        self.total_jobs = None
        self.description = description

    def start(self, total_jobs):
        self.start_time = timeit.default_timer()
        self.total_jobs = total_jobs

    def has_started(self):
        return self.start_time is not None

    def print_progress(self, num):
        current_time_taken = timeit.default_timer() - self.start_time
        time_per_job = current_time_taken / (num + 1)

        current_time_taken_str = str(datetime.timedelta(seconds=current_time_taken))

        if self.total_jobs is not None:
            estimated_total = time_per_job * self.total_jobs
            estimated_remaining = estimated_total - current_time_taken

            estimated_remaining_str = str(datetime.timedelta(seconds=estimated_remaining))

            # It is intended to print an extra newline, as this makes the progress more visible.
            print("Finished {} {} out of {}. Done {:.2f}%. Time taken {}, estimated remaining {}\n".format(
                self.description, num + 1, self.total_jobs, ((num + 1) / self.total_jobs) * 100.0,
                current_time_taken_str, estimated_remaining_str))

        else:
            print(f"Finished {self.description} {num + 1} jobs. Time taken {current_time_taken_str}.\n")

