#!/usr/bin/env python

import os, sys

import simulator.Configuration as Configuration
from simulator.Topology import Grid
from data.graph import summary, configuration_heatmap

args = sys.argv[1:]

if 'min-source-distance-heatmap' in args:
	configuration_names = Configuration.names()
	configurations = [Configuration.create_specific(name, 11, 4.5) for name in Configuration.names()]

	#print(configurations)

	#Get rid of configurations that aren't grids
	configurations = filter(lambda c: isinstance(c.topology, Grid), configurations)

	def zextractor(configuration, nid):
		return min(configuration.node_source_distance(nid, src_id) for src_id in configuration.source_ids)

	grapher = configuration_heatmap.Grapher("results/Configurations", "min-src-distance", zextractor)

	grapher.nokey = True
	grapher.xaxis_label = "X Coordinate"
	grapher.yaxis_label = "Y Coordinate"
	grapher.zaxis_label = "Minimum Source Distance (m)"

	grapher.create(configurations)

	summary_grapher = summary.GraphSummary(
	    os.path.join("results/Configurations", "min-src-distance"),
	    '{}-{}'.format("results/Configurations", "min-src-distance")
	)

	summary_grapher.width_factor = None
	summary_grapher.height = "7cm"

	summary_grapher.run()
