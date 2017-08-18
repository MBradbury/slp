#!/usr/bin/env python
from __future__ import print_function, division

import os, sys, argparse, math

from cmath import sqrt

import numpy as np

import simulator.Configuration as Configuration
from simulator.Topology import Grid
from data.graph import summary, configuration_heatmap

parser = argparse.ArgumentParser(description="Misc. Grapher", add_help=True)
parser.add_argument("--min-source-distance-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-estimate-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-meters-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-actual-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-det-heatmap", action='store_true', default=False)
parser.add_argument("--source-angle-tan-heatmap", action='store_true', default=False)

args = parser.parse_args(sys.argv[1:])

if args.min_source_distance_heatmap:
	configuration_names = Configuration.names()
	configurations = [Configuration.create_specific(name, 11, 4.5, "topology") for name in Configuration.names()]

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
	configurations = [Configuration.create_specific(name, 11, 4.5, "topology") for name in Configuration.names()]

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

	grapher.cbrange = (0, 180)

	grapher.create(configurations)

	summary_grapher = summary.GraphSummary(
	    os.path.join("results/Configurations", description),
	    '{}-{}'.format("results/Configurations", description)
	)

	summary_grapher.width_factor = None
	summary_grapher.height = "7cm"

	summary_grapher.run()

def is_valid_angle(angle):
	return not np.isinf(angle) and not np.isnan(angle) and 0 <= angle <= math.pi 

def cosine_rule(opp, adj, hyp):

	#print("opp={} adj={} hyp={}".format(opp, adj, hyp))

	try:
		temp = round(((adj * adj) + (hyp * hyp) - (opp * opp)) / (2.0 * adj * hyp), 7)

		return math.acos(temp)
	except ZeroDivisionError:
		return float('inf')


def angle_to_estimate_hops(conf, n, i):
	ssd = float(conf.ssd(i))
	dsink = float(conf.node_sink_distance(n))
	dsrc = float(conf.node_source_distance(n, i))

	return cosine_rule(ssd, dsrc, dsink)

def angle_between_estimate_hops(conf, n, i, j):
	ssd_i = conf.ssd(i)
	ssd_j = conf.ssd(j)

	dsink = conf.node_sink_distance(n)

	dsrc_i = conf.node_source_distance(n, i)
	dsrc_j = conf.node_source_distance(n, j)

	angle_i = angle_to_estimate_hops(conf, n, i)
	angle_j = angle_to_estimate_hops(conf, n, j)

	circle_angle = 2.0 * math.pi - angle_i - angle_j
	add_angle = angle_i + angle_j
	subtract_angle = abs(angle_i - angle_j)

	try:
		return min([angle for angle in [circle_angle, add_angle, subtract_angle] if is_valid_angle(angle)])
	except ValueError:
		return 0


def angle_to_estimate_meters(conf, n, i):
	ssd = conf.ssd_meters(i)
	dsink = conf.node_sink_distance_meters(n)
	dsrc = conf.node_source_distance_meters(n, i)

	return cosine_rule(ssd, dsrc, dsink)

def angle_between_estimate_meters(conf, n, i, j):
	ssd_i = conf.ssd_meters(i)
	ssd_j = conf.ssd_meters(j)

	dsink = conf.node_sink_distance_meters(n)

	dsrc_i = conf.node_source_distance_meters(n, i)
	dsrc_j = conf.node_source_distance_meters(n, j)

	angle_i = angle_to_meters(conf, n, i)
	angle_j = angle_to_meters(conf, n, j)

	circle_angle = 2.0 * math.pi - angle_i - angle_j
	add_angle = angle_i + angle_j
	subtract_angle = abs(angle_i - angle_j)

	return min([angle for angle in [circle_angle, add_angle, subtract_angle] if is_valid_angle(angle)])


def angle_between_det_meters(conf, n, i, j):
	dsrc_i = conf.node_source_distance_meters(n, i)
	dsrc_j = conf.node_source_distance_meters(n, j)

	a = conf.ssd_meters(i)
	b = conf.ssd_meters(j)

	c = conf.node_sink_distance_meters(n)

	e = dsrc_i
	f = dsrc_j

	part1 = - a**2 * b**2 + a**2 * c**2 + a**2 * f**2
	rsqrt1 = sqrt(a**4 - (2 * a**2 * c**2) - (2 * a**2 * e**2) + c**4 - (2 * c**2 * e**2) + e**4)
	rsqrt2 = sqrt(b**4 - (2 * b**2 * c**2) - (2 * b**2 * f**2) + c**4 - (2 * c**2 * f**2) + f**4)
	part2 = b**2 * c**2 + b**2 * e**2 - c**4 + c**2 * e**2 + c**2 * f**2 - e**2 * f**2

	d1 = None if c == 0 else sqrt((part1 - (rsqrt1 * rsqrt2).real + part2) / c**2) / sqrt(2)
	d2 = None if c == 0 else sqrt((part1 + (rsqrt1 * rsqrt2).real + part2) / c**2) / sqrt(2)

	d3 = None if c == 0 or (a**2 - e**2) * (b**2 - f**2) == 0 else sqrt(a**4 * (- f**2) + a**2 * b**2 * e**2 + a**2 * b**2 * f**2 + a**2 * e**2 * f**2 - a**2 * f**4 - b**4 * e**2 - b**2 * e**4 + b**2 * e**2 * f**2) / sqrt((a**2 - e**2) * (b**2 - f**2))

	print(n, i, j, conf.node_source_distance_meters(j, i), d1, d2, d3)

	distances = [d1, d2, d3]
	angles = []

	for distance in distances:
		if distance is None:
			continue

		if distance.imag != 0:
			continue

		try:
			angle = cosine_rule(distance.real, dsrc_i, dsrc_j)
			angles.append(angle)
		except ValueError:
			pass

	print(angles)
	print()

	return 0 if len(angles) == 0 else min(angles)


def angle_between_tan_meters(conf, n, i, j):
	dsrc_i = conf.node_source_distance_meters(n, i)
	dsrc_j = conf.node_source_distance_meters(n, j)

	e = conf.ssd_meters(i)
	f = conf.ssd_meters(j)

	d = conf.node_sink_distance_meters(n)

	c = dsrc_i
	g = dsrc_j

	bxp1 = (c**2 + d**2 - e**2) * (d**2 - f**2 + g**2)
	bxp2 = sqrt((c-d-e)*(c+d-e)*(c-d+e)*(c+d+e)*(d-f-g)*(d+f-g)*(d-f+g)*(d+f+g))

	byp1 = d**2 - f**2 + g**2
	byp2 = sqrt((c-d-e)*(c+d-e)*(c-d+e)*(c+d+e)*(d-f-g)*(d+f-g)*(d-f+g)*(d+f+g))
	byp3 = 2 * (d**2+e**2)*(d**2-f**2+g**2)
	byp4 = (d-e)*(d+e)*(d**2-f**2+g**2)
	byp5 = 4 * c * d**2 * sqrt(-(c-d-e)*(c+d-e)*(c-d+e)*(c+d+e))

	if byp5 == 0:
		return float('NaN')

	bx1 = (bxp1 + bxp2) / (4 * c * d**2)
	by1 = (c**4 * +byp1 + c**2 * (byp2 - byp3) + (d-e)*(d+e)*(byp2 + byp4)) / byp5

	bx2 = (bxp1 - bxp2) / (4 * c * d**2)
	by2 = (c**4 * -byp1 + c**2 * (byp2 + byp3) + (d-e)*(d+e)*(byp2 - byp4)) / byp5

	print(n, i, j, conf.node_source_distance_meters(j, i), (bx1, by1), (bx2, by2))

	if any(value.imag != 0 for value in [bx1, by1, bx2, by2]):
		raise RuntimeError("Imag")

	angle1 = math.atan2(by1.real, bx1.real)
	angle2 = math.atan2(by2.real, bx2.real)

	angles = [angle for angle in [angle1, angle2] if is_valid_angle(angle)]

	return 0 if len(angles) == 0 else min(angles)


def angle_between_actual_meters(conf, n, i, j):
	dsrc_i = conf.node_source_distance_meters(n, i)
	dsrc_j = conf.node_source_distance_meters(n, j)

	dist_i_j = conf.node_source_distance_meters(i, j)

	return cosine_rule(dist_i_j, dsrc_i, dsrc_j)

if args.source_angle_estimate_heatmap:
	def zextractor(configuration, nid):
		(a, b) = tuple(configuration.source_ids)
		angle = angle_between_estimate_hops(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	def zextractor_error(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle1 = angle_between_estimate_hops(configuration, nid, a, b) * (180.0 / math.pi)
		angle2 = angle_between_actual_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle1) or np.isnan(angle2) else abs(angle1 - angle2)

	angle_heapmaps("source_angle_estimate", zextractor)
	angle_heapmaps("source_angle_estimate_error", zextractor_error)




if args.source_angle_meters_heatmap:
	def zextractor(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle = angle_between_estimate_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	def zextractor_error(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle1 = angle_between_estimate_meters(configuration, nid, a, b) * (180.0 / math.pi)
		angle2 = angle_between_actual_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle1) or np.isnan(angle2) else abs(angle1 - angle2)

	angle_heapmaps("source_angle_meters", zextractor)
	angle_heapmaps("source_angle_meters_error", zextractor_error)


if args.source_angle_det_heatmap:
	def zextractor(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle = angle_between_det_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	def zextractor_error(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle1 = angle_between_det_meters(configuration, nid, a, b) * (180.0 / math.pi)
		angle2 = angle_between_actual_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle1) or np.isnan(angle2) else abs(angle1 - angle2)

	angle_heapmaps("source_angle_det", zextractor)
	angle_heapmaps("source_angle_det_error", zextractor_error)



if args.source_angle_tan_heatmap:
	def zextractor(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle = angle_between_tan_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	def zextractor_error(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle1 = angle_between_tan_meters(configuration, nid, a, b) * (180.0 / math.pi)
		angle2 = angle_between_actual_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle1) or np.isnan(angle2) else abs(angle1 - angle2)

	angle_heapmaps("source_angle_tan", zextractor)
	angle_heapmaps("source_angle_tan_error", zextractor_error)


if args.source_angle_actual_heatmap:
	def zextractor(configuration, nid):
		if nid in configuration.source_ids or nid == configuration.sink_id:
			return '?'

		(a, b) = tuple(configuration.source_ids)
		angle = angle_between_actual_meters(configuration, nid, a, b) * (180.0 / math.pi)
		return '?' if np.isnan(angle) else angle

	angle_heapmaps("source_angle_actual", zextractor)
