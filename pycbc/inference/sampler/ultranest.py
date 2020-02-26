# Copyright (C) 2020  Alex Nitz
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
"""
This modules provides classes and functions for using the dynesty sampler
packages for parameter estimation.
"""


from __future__ import absolute_import

import logging
import numpy

from pycbc.inference.io.ultranest import UltranestFile
from .base import (BaseSampler, setup_output)
from .. import models


#
# =============================================================================
#
#                                   Samplers
#
# =============================================================================
#

class UltranestSampler(BaseSampler):
    """This class is used to construct an Dynesty sampler from the dynesty
    package.

    Parameters
    ----------
    model : model
        A model from ``pycbc.inference.models``.
    """
    name = "ultranest"
    _io = UltranestFile

    def __init__(self, model, **kwargs):
        super(UltranestSampler, self).__init__(model)
    
        import ultranest
        model_call = UltranestModel(model)

        nprocesses = 1
        if nprocesses > 1:
            # these are used to help paralleize over multiple cores / MPI
            models._global_instance = model_call
            log_likelihood_call = _call_global_loglikelihood
            prior_call = _call_global_logprior
        else:
            prior_call = model_call.prior_transform
            log_likelihood_call = model_call.log_likelihood

        self._sampler = ultranest.ReactiveNestedSampler(
            list(self.model.variable_params),
            log_likelihood_call,
            prior_call)

        self.nlive = 0
        self.ndim = len(self.model.variable_params)
        self.result = None
        self.kwargs = kwargs  # Keywords for the run method of ultranest

    def run(self):
        self.result = self._sampler.run(**self.kwargs)

    @property
    def io(self):
        return self._io

    @property
    def niterations(self):
        return self.result['niter']

    @classmethod
    def from_config(cls, cp, model, **kwds):
        """
        Loads the sampler from the given config file.
        """
        skeys = {}
        opts = {'update_interval_iter_fraction': float,
                'update_interval_ncall': int,
                'log_interval': int,
                'show_status': bool,
                'dlogz': float,
                'dKL': float,
                'frac_remain': float,
                'Lepsilon': float,
                'min_ess': int,
                'max_iters': int,
                'max_ncalls': int,
                'max_num_improvement_loops': int,
                'min_num_live_points': int,
                'cluster_num_live_points:': int}
        for opt_name in opts:
            if cp.has_option('sampler', opt_name):
                value = cp.get('sampler', opt_name)
                skeys[opt_name] = opts[opt_name](value)
        return cls(model, **skeys)

    def checkpoint(self):
        pass

    def finalize(self):
        logging.info("Writing samples to files")
        for fn in [self.checkpoint_file, self.backup_file]:
            self.write_results(fn)

    @property
    def model_stats(self):
        return {}

    @property
    def samples(self):
        samples_dict = {p: self.result['samples'][:, i] for p, i in
                        zip(self.model.variable_params, range(self.ndim))}
        return samples_dict

    def write_results(self, filename):
        """Writes samples, model stats, acceptance fraction, and random state
        to the given file.

        Parameters
        -----------
        filename : str
            The file to write to. The file is opened using the ``io`` class
            in an an append state.
        """
        with self.io(filename, 'a') as fp:
            # write samples
            fp.write_samples(self.samples, self.model.variable_params)
            # write log evidence
            fp.write_logevidence(self.logz, self.logz_err)

    def setup_output(self, output_file):
        """Sets up the sampler's checkpoint and output files.

        The checkpoint file has the same name as the output file, but with
        ``.checkpoint`` appended to the name. A backup file will also be
        created.

        If the output file already exists, an ``OSError`` will be raised.
        This can be overridden by setting ``force`` to ``True``.

        Parameters
        ----------
        sampler : sampler instance
            Sampler
        output_file : str
            Name of the output file.
        force : bool, optional
            If the output file already exists, overwrite it.
        """
        setup_output(self, output_file)

    @property
    def logz(self):
        """
        return bayesian evidence estimated by
        dynesty sampler
        """

        return self.result['logz']

    @property
    def logz_err(self):
        """
        return error in bayesian evidence estimated by
        dynesty sampler
        """

        return self.result['logzerr']


def _call_global_loglikelihood(cube):
    return models._global_instance.log_likelihood(cube)


def _call_global_logprior(cube):
    return models._global_instance.prior_transform(cube)


class UltranestModel(object):
    """
    Class for making PyCBC Inference 'model class'
    Parameters
    ----------
    model : inference.BaseModel instance
             A model instance from pycbc.
    """

    def __init__(self, model, loglikelihood_function=None):
        if model.sampling_transforms is not None:
            raise ValueError("Ultranest does not support sampling transforms")
        self.model = model
        if loglikelihood_function is None:
            loglikelihood_function = 'loglikelihood'
        self.loglikelihood_function = loglikelihood_function

    def log_likelihood(self, cube):
        """
        returns log likelihood function
        """
        params = {p: v for p, v in zip(self.model.sampling_params, cube)}
        self.model.update(**params)
        if self.model.logprior == -numpy.inf:
            return -numpy.inf
        return getattr(self.model, self.loglikelihood_function)

    def prior_transform(self, cube):
        """
        prior transform function for ultranest sampler
        It takes unit cube as input parameter and apply
        prior transforms
        """
        cube = cube.copy()
        prior_dists = self.model.prior_distribution.distributions
        dist_dict = {}
        for dist in prior_dists:
            dist_dict.update({param: dist for param in dist.params})
        for i, param in enumerate(self.model.variable_params):
            cube[i] = dist_dict[param].cdfinv(param, cube[i])
        return cube
