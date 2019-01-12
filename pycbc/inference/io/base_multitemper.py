# Copyright (C) 2018 Collin Capano
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# self.option) any later version.
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
"""Provides I/O support for multi-tempered sampler.
"""

from __future__ import absolute_import
import argparse
from .base_mcmc import MCMCMetadataIO
import numpy
from .posterior import PosteriorFile

class ParseTempsArg(argparse.Action):
    """Argparse action that will parse temps argument.

    If the provided argument is 'all', sets 'all' in the namespace dest. If a
    a sequence of numbers are provided, converts those numbers to ints before
    saving to the namespace.
    """
    def __init__(self, type=str, **kwargs): # pylint: disable=redefined-builtin
        # check that type is string
        if type != str:
            raise ValueError("the type for this action must be a string")
        super(ParseTempsArg, self).__init__(type=type, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        singlearg = isinstance(values, (str, unicode))
        if singlearg:
            values = [values]
        if values[0] == 'all':
            # check that only a single value was provided
            if len(values) > 1:
                raise ValueError("if provide 'all', should not specify any "
                                 "other temps")
            temps = 'all'
        else:
            temps = []
            for val in values:
                try:
                    val = int(val)
                except ValueError:
                    pass
                temps.append(val)
            if singlearg:
                temps = temps[0]
        setattr(namespace, self.dest, temps)


class MultiTemperedMetadataIO(MCMCMetadataIO):
    """Adds support for reading/writing multi-tempered metadata to
    MCMCMetadatIO.
    """
    @property
    def ntemps(self):
        """Returns the number of temperatures used by the sampler."""
        return self[self.sampler_group].attrs['ntemps']

    def write_sampler_metadata(self, sampler):
        """Adds writing ntemps to file.
        """
        super(MultiTemperedMetadataIO, self).write_sampler_metadata(sampler)
        self[self.sampler_group].attrs["ntemps"] = sampler.ntemps

    @staticmethod
    def extra_args_parser(parser=None, skip_args=None, **kwargs):
        """Adds --temps to MCMCIO parser.
        """
        if skip_args is None:
            skip_args = []
        parser, actions = MCMCMetadataIO.extra_args_parser(
            parser=parser, skip_args=skip_args, **kwargs)
        if 'temps' not in skip_args:
            act = parser.add_argument(
                "--temps", nargs="+", default=0, action=ParseTempsArg,
                help="Get the given temperatures. May provide either a "
                     "sequence of integers specifying the temperatures to "
                     "plot, or 'all' for all temperatures. Default is to only "
                     "plot the coldest (= 0) temperature chain.")
            actions.append(act)
        return parser, actions


class MultiTemperedMCMCIO(object):
    """Provides functions for reading/writing samples from a parallel-tempered
    MCMC sampler.
    """
    def write_samples(self, samples, parameters=None,
                      start_iteration=None, max_iterations=None):
        """Writes samples to the given file.

        Results are written to ``samples_group/{vararg}``, where ``{vararg}``
        is the name of a model params. The samples are written as an
        ``ntemps x nwalkers x niterations`` array.

        Parameters
        -----------
        samples : dict
            The samples to write. Each array in the dictionary should have
            shape nwalkers x niterations.
        parameters : list, optional
            Only write the specified parameters to the file. If None, will
            write all of the keys in the ``samples`` dict.
        start_iteration : int, optional
            Write results to the file's datasets starting at the given
            iteration. Default is to append after the last iteration in the
            file.
        max_iterations : int, optional
            Set the maximum size that the arrays in the hdf file may be resized
            to. Only applies if the samples have not previously been written
            to file. The default (None) is to use the maximum size allowed by
            h5py.
        """
        ntemps, nwalkers, niterations = samples.values()[0].shape
        assert all(p.shape == (ntemps, nwalkers, niterations)
                   for p in samples.values()), (
               "all samples must have the same shape")
        if max_iterations is not None and max_iterations < niterations:
            raise IndexError("The provided max size is less than the "
                             "number of iterations")
        group = self.samples_group + '/{name}'
        if parameters is None:
            parameters = samples.keys()
        # loop over number of dimensions
        for param in parameters:
            dataset_name = group.format(name=param)
            istart = start_iteration
            try:
                fp_niterations = self[dataset_name].shape[-1]
                if istart is None:
                    istart = fp_niterations
                istop = istart + niterations
                if istop > fp_niterations:
                    # resize the dataset
                    self[dataset_name].resize(istop, axis=2)
            except KeyError:
                # dataset doesn't exist yet
                if istart is not None and istart != 0:
                    raise ValueError("non-zero start_iteration provided, "
                                     "but dataset doesn't exist yet")
                istart = 0
                istop = istart + niterations
                self.create_dataset(dataset_name, (ntemps, nwalkers, istop),
                                    maxshape=(ntemps, nwalkers,
                                              max_iterations),
                                    dtype=samples[param].dtype,
                                    fletcher32=True)
            self[dataset_name][:, :, istart:istop] = samples[param]

    def read_raw_samples(self, fields,
                         thin_start=None, thin_interval=None, thin_end=None,
                         iteration=None, temps='all', walkers=None,
                         flatten=True):
        """Base function for reading samples.

        Parameters
        -----------
        fields : list
            The list of field names to retrieve. Must be names of datasets in
            the ``samples_group``.
        thin_start : int, optional
            Start reading from the given iteration. Default is to start from
            the first iteration.
        thin_interval : int, optional
            Only read every ``thin_interval`` -th sample. Default is 1.
        thin_end : int, optional
            Stop reading at the given iteration. Default is to end at the last
            iteration.
        iteration : int, optional
            Only read the given iteration. If this provided, it overrides
            the ``thin_(start|interval|end)`` options.
        temps : 'all' or (list of) int, optional
            The temperature index (or list of indices) to retrieve. To retrieve
            all temperates pass 'all', or a list of all of the temperatures.
            Default is 'all'.
        walkers : (list of) int, optional
            Only read from the given walkers. Default is to read all.
        flatten : bool, optional
            Flatten the samples to 1D arrays before returning. Otherwise, the
            returned arrays will have shape (requested temps x
            requested walkers x requested iteration(s)). Default is True.

        Returns
        -------
        array_class
            An instance of the given array class populated with values
            retrieved from the fields.
        """
        if isinstance(fields, (str, unicode)):
            fields = [fields]
        # walkers to load
        if walkers is not None:
            widx = numpy.zeros(self.nwalkers, dtype=bool)
            widx[walkers] = True
            nwalkers = widx.sum()
        else:
            widx = slice(None, None)
            nwalkers = self.nwalkers
        # temperatures to load
        selecttemps = False
        if isinstance(temps, int):
            tidx = temps
            ntemps = 1
        else:
            # temps is either 'all' or a list of temperatures;
            # in either case, we'll get all of the temperatures from the file;
            # if not 'all', then we'll pull out the ones we want
            tidx = slice(None, None)
            selecttemps = temps != 'all'
            if selecttemps:
                ntemps = len(temps)
            else:
                ntemps = self.ntemps
        # get the slice to use
        if iteration is not None:
            get_index = int(iteration)
            niterations = 1
        else:
            get_index = self.get_slice(thin_start=thin_start,
                                       thin_end=thin_end,
                                       thin_interval=thin_interval)
            # we'll just get the number of iterations from the returned shape
            niterations = None
        # load
        group = self.samples_group + '/{name}'
        arrays = {}
        for name in fields:
            arr = self[group.format(name=name)][tidx, widx, get_index]
            if niterations is None:
                niterations = arr.shape[-1]
            # pull out the temperatures we need
            if selecttemps:
                arr = arr[temps, ...]
            if flatten:
                arr = arr.flatten()
            else:
                # ensure that the returned array is 3D
                arr = arr.reshape((ntemps, nwalkers, niterations))
            arrays[name] = arr
        return arrays

    def write_posterior(self, filename, **kwargs):
        """Write posterior only file

        Parameters
        ----------
        filename : str
            Name of output file to store posterior
        """
        f = h5py.File(filename, 'w')

        # Preserve top-level metadata
        for key in self.attrs:
            f.attrs[key] = self.attrs[key]

        f.attrs['filetype'] = PosteriorFile.name
        s = f.create_group('samples')
        fields = self[self.samples_group].keys()

        # Copy and squash fields into one dimensional arrays
        for field_name in fields:
            fvalue = self[self.samples_group][field_name][:]
            thin = fvalue[0,:,self.thin_start:self.thin_end:self.thin_interval]
            s[field_name] = thin.flatten()
