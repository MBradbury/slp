#!/usr/bin/python
# TODO: Eventually replace this using C++
# Python bindings will be slow

from TOSSIM import *

import sys
import random

t = Tossim([])
r = t.radio()

t.addChannel("Boot", sys.stdout)
t.addChannel("SourceBroadcasterC", sys.stdout)

pos_to_id = {}

def setup_boot_times(size):
	for i in xrange(1, size*size + 1):
		node = t.getNode(i)

		# All nodes will booth within the first second
		time_to_boot = int(t.ticksPerSecond() * random.random())

		print("Booting {0} at {1}".format(i, time_to_boot))
		node.bootAtTime(time_to_boot)

def create_grid(size):
	def add(coords, neighbour_coords):

		(nrow, ncol) = neighbour_coords

		# Check neighbour is valid
		if nrow >= 0 and nrow < size and ncol >= 0 and ncol < size:

			r.add(pos_to_id[coords], pos_to_id[neighbour_coords], -50.0)

			connected = r.connected(pos_to_id[coords], pos_to_id[neighbour_coords])

			print("Added link: {0} <-> {1} ({2})".format(coords, neighbour_coords, connected))

	node_counter = 1
	for row in range(size):
		for col in range(size):
			coords = (row, col)

			pos_to_id[coords] = node_counter
			node_counter += 1

	for row in range(size):
		for col in range(size):
			coords = (row, col)

			add(coords, (row, col - 1)) # Left
			add(coords, (row, col + 1)) # Right
			add(coords, (row - 1, col)) # Above
			add(coords, (row + 1, col)) # Below

def setup_noise_model(size):
	for i in xrange(1, size*size + 1):

		node = t.getNode(i)

		# Create random noise stream
		for x in xrange(500):
			node.addNoiseTraceReading(int(random.random() * 10) - 80)

		print("Created noise model for {0}".format(i))
		node.createNoiseModel()

def print_matrix(A):
	for i in range(len(A)):
		for j in range(len(A[i])):
			value = A[i][j]
			print '{:5}'.format(value if value else ""),
		print

def show_network_matrix(size):
	connected_matrix = [[pos_to_id[(x, y)] for y in xrange(size)] for x in xrange(size)]
	print_matrix(connected_matrix)

def show_node_relation_matrix(fn):
	# Create matrix
	matrix = [[0 for x in xrange(size*size+1)] for x in xrange(size*size+1)] 

	# Set up labels
	for x in xrange(size*size+1):
		matrix[0][x] = x
		matrix[x][0] = x

	# Fill in matrix
	for i in xrange(1, size*size + 1):
		for j in xrange(1, size*size + 1):
			matrix[i][j] = fn(i, j)

	print_matrix(matrix)


size = 3

setup_boot_times(size)
create_grid(size)
setup_noise_model(size)

print
show_network_matrix(size)
print
show_node_relation_matrix(r.connected)
print
show_node_relation_matrix(r.gain)
print

t.runNextEvent()
time = t.time()
while time + (20 * t.ticksPerSecond()) > t.time():
	t.runNextEvent()
