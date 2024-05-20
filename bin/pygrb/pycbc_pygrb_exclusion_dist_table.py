#!/usr/bin/env python

# Copyright (C) 2024 Jacob Buchanan
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Create table of exclusion distances."""

import sys
import argparse
import json
import pycbc.version
import pycbc.results


__author__ = "Jacob Buchanan <jacob.buchanan@ligo.org>"
__version__ = pycbc.version.git_verbose_msg
__date__ = pycbc.version.date
__program__ = "pycbc_pygrb_exclusion_dist_table"

parser = argparse.ArgumentParser(description=__doc__, formatter_class=
                                 argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--version", action="version", version=__version__)
parser.add_argument("--input-files", nargs="+", required=True,
                    help="List of JSON input files" +
                    " containing exclusion distances.")
parser.add_argument("--output-file", required=True,
                    help="Output file containing table" +
                    " of exclusion distances.")
opts = parser.parse_args()

# Load JSON files
file_contents = []
for file_name in opts.input_files:
    with open(file_name, "r") as file:
        file_contents.append(json.load(file))

# Get sorted list of trials
trials = []
for file_content in file_contents:
    trials.extend(file_content["trial_name"])
trials = list(set(trials))
trials.sort()

# Get names of injection sets
injection_sets = []
for file_content in file_contents:
    injection_sets.extend(file_content["injection_set"])
injection_sets = list(set(injection_sets))

# Headers
headers = ["Trial Name (percent)"]
for injection_set in injection_sets:
    headers.append(injection_set)

exclusion_distances = {}
for file_content in file_contents:
    if file_content["trial_name"] not in exclusion_distances:
        exclusion_distances[file_content["trial_name"]] = {}
    exclusion_distances[file_content["trial_name"]][file_content["injection_set"]] = {}
    for percent in ('50%', '90%'):
        exclusion_distances[file_content["trial_name"]][file_content["injection_set"]][percent] = \
            file_content["exclusion_distance"][percent]


# Table data
data = []
for trial in trials:
    for percent in ('50%', '90%'):
        row = [f"{trial} ({percent})"]
        for injection_set in injection_sets:
            row.append(exclusion_distances[trial][injection_set][percent])
        data.append(row)

# Sort by trial name
data.sort(key=lambda x: x[0])

# Write table
html = str(pycbc.results.static_table(headers, data))

title = "Exclusion Distances"
caption = "Table of exclusion distances for each trial and injection set."

pycbc.results.save_fig_with_metadata(html, opts.output_file,
                                     cmd=' '.join(sys.argv),
                                     title=title, caption=caption)
