import time

class SubprocessPool:
	def __init__(self, max_processes, starter, callback):
		self.max_processes = max_processes
		self.starter = starter
		self.callback = callback
		self.active = []

	def run(self, count):
		processes_finished = 0

		while processes_finished != count:

			while len(self.active) < self.max_processes and processes_finished + len(self.active) + 1 <= count:
				proc = self.starter()

				self.active.append(proc)

			time.sleep(0.1)

			new_active = []

			for proc in self.active:
				proc.poll()

				if proc.returncode is not None:
					self.callback(proc)
					processes_finished += 1
				else:
					new_active.append(proc)

			self.active = new_active

		return processes_finished
