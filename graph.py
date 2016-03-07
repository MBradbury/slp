#!/usr/bin/env python

import os, sys, argparse, math

import numpy as np

import simulator.Configuration as Configuration
from simulator.Topology import Grid
from data.graph import summary, configuration_heatmap

parser = argparse.ArgumentParser(description="Misc. Grapher", add_help=True)
parser.add_argument("--min-source-distance-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-estimate-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-meters-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-actual-heatmap", action='store_true', default=False)

args = parser.parse_args(sys.argv[1:])

if args.min_source_distance_heatmap:
	configuration_names = Configuration.names()
	configurations = [Configuration.create_specific(name, 11, 4.5) for name in Configuration.names()]

	#Get rid of configurations that aren't grids
	configurations = filter(lambda c: isinstance(c.topology, Grid), configurations)

	def zextractor(configuration, nid):
		return min(configuration.node_source_distance(nid, src_id) for src_id in configuration.source_ids)

	grapher = configuration_heatmap.Grapher("results/Configurations", "min-src-distance", zextractor)

	grapher.nokey = True
	grapher.xaxis_label = "X Coordinate"
	grapher.yaxis_label = "Y Coordinate"
	grapher.cb_label = "Minimum Source Distance (m)"

	grapher.create(configurations)

	summary_grapher = summary.GraphSummary(
	    os.path.join("results/Configurations", "min-src-distance"),
	    '{}-{}'.format("results/Configurations", "min-src-distance")
	)

	summary_grapher.width_factor = None
	summary_grapher.height = "7cm"

	summary_grapher.run()




def angle_heapmaps(description, zextractor):
	configuration_names = Configuration.names()
	configurations = [Configuration.create_specific(name, 11, 4.5) for name in Configuration.names()]

	#Get rid of configurations that aren't grids
	configurations = filter(lambda c: isinstance(c.topology, Grid), configurations)

	# Get rid of configurations that do not have 2 sources
	configurations = filter(lambda c: len(c.source_ids) == 2, configurations)

	grapher = configuration_heatmap.Grapher("results/Configurations", description, zextractor)

	grapher.nokey = True
	grapher.xaxis_label = "X Coordinate"
	grapher.yaxis_label = "Y Coordinate"
	grapher.cb_label = "Source Angle"

	grapher.dgrid3d_dimensions = "11,11"

	grapher.create(configurations)

	summary_grapher = summary.GraphSummary(
	    os.path.join("results/Configurations", description),
	    '{}-{}'.format("results/Configurations", description)
	)

	summary_grapher.width_factor = None
	summary_grapher.height = "7cm"

	summary_grapher.run()

if args.source_angle_estimate_heatmap:
	def angle_to(conf, n, i):
		ssd = conf.ssd(i)
		dsink = conf.node_sink_distance(n)
		dsrc = conf.node_source_distance(n, i)

		temp = ((dsrc * dsrc) + (dsink * dsink) - (ssd * ssd)) / (2.0 * dsrc * dsink)

		return math.acos(temp)

	def angle_between(conf, n, i, j):
		ssd_i = conf.ssd(i)
		ssd_j = conf.ssd(j)

		dsink = conf.node_sink_distance(n)

		dsrc_i = conf.node_source_distance(n, i)
		dsrc_j = conf.node_source_distance(n, j)

		angle_i = angle_to(conf, n, i)
		angle_j = angle_to(conf, n, j)

		return abs(angle_i - angle_j)

#		if (dsrc_i >= dsink and dsrc_j >= dsink) or (dsink >= ssd_i and dsink >= ssd_j):
#			return angle_i + angle_j
#		elif dsrc_i <= ssd_i and dsrc_j <= ssd_j:
#			return 2.0 * math.pi - angle_i - angle_j
#		else:
#			return abs(angle_i - angle_j)

	def zextractor(configuration, nid):
		(a, b) = tuple(configuration.source_ids)
		angle = angle_between(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	angle_heapmaps("source_angle_estimate", zextractor)




if args.source_angle_meters_heatmap:
	def angle_to_meters(conf, n, i):
		ssd = conf.ssd_meters(i)
		dsink = conf.node_sink_distance_meters(n)
		dsrc = conf.node_source_distance_meters(n, i)

		temp = round(((dsrc * dsrc) + (dsink * dsink) - (ssd * ssd)) / (2.0 * dsrc * dsink), 7)

		return math.acos(temp)

	def angle_between_meters(conf, n, i, j):
		ssd_i = conf.ssd_meters(i)
		ssd_j = conf.ssd_meters(j)

		dsink = conf.node_sink_distance_meters(n)

		dsrc_i = conf.node_source_distance_meters(n, i)
		dsrc_j = conf.node_source_distance_meters(n, j)

		angle_i = angle_to_meters(conf, n, i)
		angle_j = angle_to_meters(conf, n, j)

		if (dsrc_i >= dsink and dsrc_j >= dsink) or (dsrc_i <= ssd_i and dsrc_j <= ssd_j and dsink >= ssd_i and dsink >= ssd_j):
			return angle_i + angle_j
		elif dsrc_i <= ssd_i and dsrc_j <= ssd_j and dsink < ssd_i and dsink < ssd_j:
			return 2.0 * math.pi - angle_i - angle_j
		else:
			return abs(angle_i - angle_j)

	def zextractor(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle = angle_between_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	angle_heapmaps("source_angle_meters", zextractor)




if args.source_angle_actual_heatmap:
	def angle_between_actual(conf, n, i, j):
		dsrc_i = conf.node_source_distance_meters(n, i)
		dsrc_j = conf.node_source_distance_meters(n, j)

		dist_i_j = conf.node_source_distance_meters(i, j)

		temp = round(((dsrc_i * dsrc_i) + (dsrc_j * dsrc_j) - (dist_i_j * dist_i_j)) / (2.0 * dsrc_i * dsrc_j), 7)

		return math.acos(temp)

	def zextractor(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle = angle_between_actual(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	angle_heapmaps("source_angle_actual", zextractor)
