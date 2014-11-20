#!/usr/bin/env python

from __future__ import print_function

import math

from simulator.Configuration import *

class Calculator:

	# The time it takes for one message to be sent from
	# one node to another in seconds.
	alpha = 0.0051

	def __init__(self, configuration, source_period, num_fake_to_send):
		self.configuration = configuration
		self.source_period = float(source_period)
		self.num_fake_to_send = int(num_fake_to_send)

	def one_hop_neighbours(self, node):
		return self.configuration.one_hop_neighbours(node)

	def ssd(self):
		"""The number of hops between the sink and the source nodes"""
		return self.configuration.ssd()

	def node_sink_distance(self, node):
		return self.configuration.node_sink_distance(node)

	def node_source_distance(self, node):
		return self.configuration.node_source_distance(node)

	def attacker_source_distance(self, i):
		return max(0, self.ssd() - i)

	def send_time_Normal_Source(self, i):
		"""The time at which the source sends the ith Normal message"""
		return (i - 1) * self.source_period

	def rcv_time_Normal_Attacker(self, i):
		"""The time at which the attacker will receive the ith Normal Message,
		assuming that an attacker never receives a non-Normal message."""
		# Use the distance at the (i - 1)th Normal message as that is where
		# the attacker currently is
		return self.send_time_Normal_Source(i) + self.attacker_source_distance(i - 1) * self.alpha

	def send_time_Away_Sink(self):
		"""The time at which the sink bcasts the Away message"""
		# The code waits for Psrc / 2 seconds before sending the away message
		return self.send_time_Normal_Source(1) + self.alpha * self.ssd() + self.source_period / 2.0

	def rcv_time_Away_Normal(self, node):
		"""The time at which the given node will receive the Away message"""
		return self.send_time_Away_Sink() + self.alpha * self.node_sink_distance(node)



	def become_TFS_time(self, node):
		if node == self.configuration.sinkId or node == self.configuration.sourceId:
			raise RuntimeError("The node {} cannot become a TFS".format(node))
		elif node in self.one_hop_neighbours(self.configuration.sinkId):
			return self.rcv_time_Away_Normal(node)
		else:
			k = None
			for k in self.one_hop_neighbours(node):
				if self.node_sink_distance(k) < self.node_sink_distance(node):
					break

			return self.become_TFS_time(k) + self.tfs_duration(k) + self.alpha

	def num_Normal_sent_at_become_TFS(self, node):
		return math.ceil(self.become_TFS_time(node) / self.source_period)


	def tfs_Fake_to_send(self, node):
		if self.node_sink_distance(node) == 1:
			return self.node_sink_distance(node) + (self.ssd() - self.attacker_source_distance(self.num_Normal_sent_at_become_TFS(node)))
		else:
			return self.num_fake_to_send

	def tfs_period(self, node):
		return self.tfs_duration(node) / self.tfs_Fake_to_send(node)

	def tfs_duration(self, node):
		return self.rcv_time_Normal_Attacker(self.num_Normal_sent_at_become_TFS(node) + 1) - self.become_TFS_time(node) - self.alpha
		#return self.source_period - 2.0 * self.alpha * self.node_sink_distance(node)

calc = Calculator(CreateSourceCorner(11, 4.5), source_period=1, num_fake_to_send=4)

print(calc.configuration)
print(calc.configuration.topology.nodes)

print("SSD: {}".format(calc.ssd()))

print(calc.send_time_Away_Sink())

print("Times 1HopN(sink) rcv Away:")
for one_hop_neighbour in calc.one_hop_neighbours(calc.configuration.sinkId):
	print("\t{}: {}".format(one_hop_neighbour, calc.rcv_time_Away_Normal(one_hop_neighbour)))

for n in xrange(calc.configuration.sinkId + 1, calc.configuration.sinkId + 5):
	print("Node {}:".format(n))
	print("\tBecome TFS time is {}".format(calc.become_TFS_time(n)))
	print("\tNumber of Fake to send = {}".format(calc.tfs_Fake_to_send(n)))
	print("\tDuration        is {}".format(calc.tfs_duration(n)))
	print("\tPeriod          is {}".format(calc.tfs_period(n)))
