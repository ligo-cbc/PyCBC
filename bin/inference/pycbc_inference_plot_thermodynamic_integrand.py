#!/usr/bin/env python

# Copyright (C) 2019 Steven Reyes 
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


#
# =============================================================================
#
#                                   Preamble
#
# =============================================================================
#

import argparse
import matplotlib
matplotlib.use("agg")
from matplotlib import rc
import matplotlib.pyplot as plt
import numpy
from pycbc.inference import io
import pycbc.version

rc('text', usetex=True)

parser = argparse.ArgumentParser()
parser.add_argument("--inference-file",
                    help="The PyCBC multi-temper inference file.")
parser.add_argument("--thin-start", type=int, default=None,
                    help="MCMC iteration to begin for samples.")
parser.add_argument("--thin-end", type=int, default=None)
parser.add_argument("--thin-interval", type=int, default=None)
parser.add_argument("--beta-log-scale", action="store_true")
parser.add_argument("--integrand-logarithmic", action="store_true")
parser.add_argument("--output-file", type=str)
args = parser.parse_args()

# Read in the necessary data
fp = io.loadfile(args.inference_file, "r")
logl = fp.read_samples("loglikelihood", thin_start=args.thin_start,
                       thin_end=args.thin_end,
                       thin_interval=args.thin_interval,
                       flatten=False)["loglikelihood"]
betas = fp["sampler_info"].attrs["betas"]
fp.close()

# Correctly order all of the betas and log likelihoods
order = numpy.argsort(betas)
betas = betas[order]
logl = logl[order]

if args.beta_log_scale:
    plt.xscale("log")

if args.integrand_logarithmic:
    y = betas * numpy.average(logl, axis=(1,2))
    plt.ylabel(r"$\beta \, \langle ln \, \mathcal{L} \rangle_\beta$")

else:
    y = numpy.average(logl, axis=(1,2))
    plt.ylabel(r"$\langle ln \, \mathcal{L} \rangle_\beta$")

plt.minorticks_on()
plt.grid(True, which='minor', axis='y', ls="--", alpha=0.2)
plt.grid(True, which='major', axis='y', ls="-", alpha=0.4)
plt.grid(True, which='major', axis='x', ls="-", alpha=0.4)

plt.plot(betas, y, marker="v")
plt.xlabel(r"$\beta$")

plt.tight_layout()
plt.savefig(args.output_file, dpi=200)
