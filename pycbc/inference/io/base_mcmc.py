# Copyright (C) 2016 Christopher M. Biwer, Collin Capano
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
"""Provides I/O that is specific to MCMC samplers.
"""

from __future__ import (absolute_import, division)

from six import string_types

import numpy
import argparse


class CommonMCMCMetadataIO(object):
    """Provides functions for reading/writing MCMC metadata to file.

    The functions here are common to both standard MCMC (in which chains
    are independent) and ensemble MCMC (in which chains/walkers share
    information).
    """
    def write_resume_point(self):
        """Keeps a list of the number of iterations that were in a file when a
        run was resumed from a checkpoint."""
        try:
            resume_pts = self.attrs["resume_points"].tolist()
        except KeyError:
            resume_pts = []
        try:
            niterations = self.niterations
        except KeyError:
            niterations = 0
        resume_pts.append(niterations)
        self.attrs["resume_points"] = resume_pts

    def write_niterations(self, niterations):
        """Writes the given number of iterations to the sampler group."""
        self[self.sampler_group].attrs['niterations'] = niterations

    @property
    def niterations(self):
        """Returns the number of iterations the sampler was run for."""
        return self[self.sampler_group].attrs['niterations']

    @property
    def nwalkers(self):
        """Returns the number of walkers used by the sampler.

        Alias of ``nchains``.
        """
        try:
            return self[self.sampler_group].attrs['nwalkers']
        except KeyError:
            return self[self.sampler_group].attrs['nchains']

    @property
    def nchains(self):
        """Returns the number of chains used by the sampler.

        Alias of ``nwalkers``.
        """
        try:
            return self[self.sampler_group].attrs['nchains']
        except KeyError:
            return self[self.sampler_group].attrs['nwalkers']

    def _thin_data(self, group, params, thin_interval):
        """Thins data on disk by the given interval.

        This makes no effort to record the thinning interval that is applied.

        Parameters
        ----------
        group : str
            The group where the datasets to thin live.
        params : list
            The list of dataset names to thin.
        thin_interval : int
            The interval to thin the samples on disk by.
        """
        samples = self.read_raw_samples(params, thin_start=0,
                                        thin_interval=thin_interval,
                                        thin_end=None, flatten=False,
                                        group=group)
        # now resize and write the data back to disk
        fpgroup = self[group]
        for param in params:
            data = samples[param]
            # resize the arrays on disk
            fpgroup[param].resize(data.shape)
            # and write
            fpgroup[param][:] = data

    def thin(self, thin_interval):
        """Thins the samples on disk to the given thinning interval.

        The interval must be a multiple of the file's current ``thinned_by``.

        Parameters
        ----------
        thin_interval : int
            The interval the samples on disk should be thinned by.
        """
        # get the new interval to thin by
        new_interval = thin_interval / self.thinned_by
        if new_interval % 1:
            raise ValueError("thin interval ({}) must be a multiple of the "
                             "current thinned_by ({})"
                             .format(thin_interval, self.thinned_by))
        new_interval = int(new_interval)
        # now thin the data on disk
        params = list(self[self.samples_group].keys())
        self._thin_data(self.samples_group, params, new_interval)
        # store the interval that samples were thinned by
        self.thinned_by = thin_interval
        # If a default thin interval and thin start exist, reduce them by the
        # thinned interval. If the thin interval is not an integer multiple
        # of the original, we'll round up, to avoid getting samples from
        # before the burn in / at an interval less than the ACL.
        self.thin_start = int(numpy.ceil(self.thin_start/new_interval))
        self.thin_interval = int(numpy.ceil(self.thin_interval/new_interval))

    @property
    def thinned_by(self):
        """Returns interval samples have been thinned by on disk.

        This looks for ``thinned_by`` in the samples group attrs. If none is
        found, will just return 1.
        """
        try:
            thinned_by = self.attrs['thinned_by']
        except KeyError:
            thinned_by = 1
        return thinned_by

    @thinned_by.setter
    def thinned_by(self, thinned_by):
        """Sets the thinned_by attribute.

        This is the interval that samples have been thinned by on disk. The
        given value is written to
        ``self[self.samples_group].attrs['thinned_by']``.
        """
        self.attrs['thinned_by'] = int(thinned_by)

    def last_iteration(self, parameter=None, group=None):
        """Returns the iteration of the last sample of the given parameter.

        Parameters
        ----------
        parameter : str, optional
            The name of the parameter to get the last iteration for. If
            None provided, will just use the first parameter in ``group``.
        group : str, optional
            The name of the group to get the last iteration from. Default is
            the ``samples_group``.
        """
        if group is None:
            group = self.samples_group
        if parameter is None:
            try:
                parameter = list(self[group].keys())[0]
            except (IndexError, KeyError):
                # nothing has been written yet, just return 0
                return 0
        try:
            lastiter = self[group][parameter].shape[-1]
        except KeyError:
            # no samples have been written, just return 0
            lastiter = 0
        # account for thinning
        return lastiter * self.thinned_by

    def iterations(self, parameter):
        """Returns the iteration each sample occurred at."""
        return numpy.arange(0, self.last_iteration(parameter), self.thinned_by)

    def write_sampler_metadata(self, sampler):
        """Writes the sampler's metadata."""
        self.attrs['sampler'] = sampler.name
        try:
            self[self.sampler_group].attrs['nchains'] = sampler.nchains
        except ValueError:
            self[self.sampler_group].attrs['nwalkers'] = sampler.nwalkers
        # write the model's metadata
        sampler.model.write_metadata(self)

    @property
    def is_burned_in(self):
        """Returns whether or not chains are burned in.

        Raises a ``ValueError`` if no burn in tests were done.
        """
        try:
            return self[self.sampler_group]['is_burned_in'][()]
        except KeyError:
            raise ValueError("No burn in tests were performed")

    @property
    def burn_in_iteration(self):
        """Returns the burn in iteration of all the chains.

        Raises a ``ValueError`` if no burn in tests were done.
        """
        try:
            return self[self.sampler_group]['burn_in_iteration'][()]
        except KeyError:
            raise ValueError("No burn in tests were performed")

    @property
    def burn_in_index(self):
        """Returns the burn in index.

        This is the burn in iteration divided by the file's ``thinned_by``.
        Requires the class that this is used with has a ``burn_in_iteration``
        attribute.
        """
        return self.burn_in_iteration // self.thinned_by

    @property
    def acl(self):
        """Returns the ACL.

        Raises a ``ValueError`` if the ACL has not been calculated.
        """
        try:
            return self[self.sampler_group]['acl'][()]
        except KeyError:
            raise ValueError("ACL has not been calculated")

    @acl.setter
    def acl(self, acl):
        """Writes the autocorrelation length(s).

        ACL(s) are written to the ``sample_group`` as a dataset with name
        ``acl``.

        Parameters
        ----------
        acl : array or int
            ACL(s) to write.
        """
        # pylint: disable=no-member
        self.write_data('acl', acl, path=self.sampler_group)

    @property
    def raw_acls(self):
        """Dictionary of parameter names -> raw autocorrelation length(s).

        Depending on the sampler, the autocorrelation lengths may be integers,
        or [ntemps x] [nchains x] arrays.

        Raises a ``ValueError`` is no raw acls have been set.
        """
        try:
            group = self[self.samper_group]['raw_acls']
        except KeyError:
            raise ValueError("ACLs have not been calculated")
        acls = {}
        for param in group:
            acls[param] = group[param][()]
        return acls

    @raw_acls.setter
    def raw_acls(self, acls):
        """Writes the raw autocorrelation lengths.

        The ACL of each parameter is saved to
        ``[sampler_group]/raw_acls/{param}']``. Works for all types of MCMC
        samplers (independent chains, ensemble, parallel tempering).

        Parameters
        ----------
        acls : dict
            A dictionary of ACLs keyed by the parameter.
        """
        path = self.sampler_group + '/raw_acls'
        for param in acls:
            self.write_data(param, acls[param], path=path)

    def write_acls(self, acl, raw_acls):
        """Writes both the acl and raw acls.

        Parameters
        ----------
        acl : array or int
            The autocorrelation length. See the ``acl`` attribute for details.
        raw_acls : dict
            Dictionary of parameter names -> acls. See the ``raw_acls``
            attribute for details.
        """
        self.acl = acl
        self.raw_acls = raw_acls

    @staticmethod
    def extra_args_parser(parser=None, skip_args=None, **kwargs):
        """Create a parser to parse sampler-specific arguments for loading
        samples.

        Parameters
        ----------
        parser : argparse.ArgumentParser, optional
            Instead of creating a parser, add arguments to the given one. If
            none provided, will create one.
        skip_args : list, optional
            Don't parse the given options. Options should be given as the
            option string, minus the '--'. For example,
            ``skip_args=['iteration']`` would cause the ``--iteration``
            argument not to be included.
        \**kwargs :
            All other keyword arguments are passed to the parser that is
            created.

        Returns
        -------
        parser : argparse.ArgumentParser
            An argument parser with th extra arguments added.
        actions : list of argparse.Action
            A list of the actions that were added.
        """
        if parser is None:
            parser = argparse.ArgumentParser(**kwargs)
        elif kwargs:
            raise ValueError("No other keyword arguments should be provded if "
                             "a parser is provided.")
        if skip_args is None:
            skip_args = []
        actions = []
        if 'thin-start' not in skip_args:
            act = parser.add_argument(
                "--thin-start", type=int, default=None,
                help="Sample number to start collecting samples. If "
                     "none provided, will use the input file's `thin_start` "
                     "attribute.")
            actions.append(act)
        if 'thin-interval' not in skip_args:
            act = parser.add_argument(
                "--thin-interval", type=int, default=None,
                help="Interval to use for thinning samples. If none provided, "
                     "will use the input file's `thin_interval` attribute.")
            actions.append(act)
        if 'thin-end' not in skip_args:
            act = parser.add_argument(
                "--thin-end", type=int, default=None,
                help="Sample number to stop collecting samples. If "
                     "none provided, will use the input file's `thin_end` "
                     "attribute.")
            actions.append(act)
        if 'iteration' not in skip_args:
            act = parser.add_argument(
                "--iteration", type=int, default=None,
                help="Only retrieve the given iteration. To load "
                     "the last n-th sampe use -n, e.g., -1 will "
                     "load the last iteration. This overrides "
                     "the thin-start/interval/end options.")
            actions.append(act)
        if 'walkers' not in skip_args:
            act = parser.add_argument(
                "--walkers", "--chains", type=int, nargs="+", default=None,
                help="Only retrieve samples from the listed "
                     "walkers/chains. Default is to retrieve from all "
                     "walkers/chains.")
            actions.append(act)
        return parser, actions


class MCMCMetadataIO(object):
    """Provides functions for reading/writing metadata to file for MCMCs in
    which all chains are independent of each other.

    Overrides the ``BaseInference`` file's ``thin_start`` and ``thin_interval``
    attributes. Instead of integers, these return arrays.
    """
    @property
    def thin_start(self):
        """Returns the default thin start to use for reading samples.

        If burn-in tests were done, this will return the burn-in index of every
        chain that has burned in. The start index for chains that have not
        burned in will be greater than the number of samples, so that those
        chains return no samples. If no burn-in tests were done, returns 0
        for all chains.
        """
        try:
            thin_start = self.burn_in_index
            # replace any that have not been burned in with the number
            # of iterations; this will cause those chains to not return
            # any samples
            thin_start[~self.is_burned_in] = \
                int(numpy.ceil(self.niterations/self.thinned_by))
            return thin_start
        except ValueError:
            # no burn in, just return array of zeros
            return numpy.zeros(self.nchains, dtype=int)

    @property
    def thin_interval(self):
        """Returns the default thin interval to use for reading samples.

        If a finite ACL exists in the file, will return that. Otherwise,
        returns 1.
        """
        try:
            acl = self.acl
        except ValueError:
            return numpy.ones(self.nchains, dtype=int)
        # replace any infs with the number of samples
        acl[numpy.isinf(acl)] = self.niterations / self.thinned_by
        return numpy.ceil(acl).astype(int)


class EnsembleMCMCMetadataIO(object):
    """Provides functions for reading/writing metadata to file for ensemble
    MCMCs.
    """
    @property
    def thin_start(self):
        """Returns the default thin start to use for reading samples.

        If burn-in tests were done, returns the burn in index. Otherwise,
        returns 0.
        """
        try:
            return self.burn_in_index
        except ValueError:
            # no burn in, just return 0
            return 0

    @property
    def thin_interval(self):
        """Returns the default thin interval to use for reading samples.

        If a finite ACL exists in the file, will return that. Otherwise,
        returns 1.
        """
        try:
            acl = self.acl
        except ValueError:
            acl = 1
        if numpy.isfinite(acl):
            acl = int(numpy.ceil(acl))
        else:
            acl = 1
        return acl


def write_samples(fp, samples, parameters=None, last_iteration=None,
                  samples_group=None, thin_by=None):
    """Writes samples to the given file.

    This works for both standard MCMC and ensemble MCMC samplers without
    parallel tempering.

    Results are written to ``samples_group/{vararg}``, where ``{vararg}``
    is the name of a model params. The samples are written as an
    ``nwalkers x niterations`` array. If samples already exist, the new
    samples are appended to the current.

    If the current samples on disk have been thinned (determined by the
    ``thinned_by`` attribute in the samples group), then the samples will
    be thinned by the same amount before being written. The thinning is
    started at the sample in ``samples`` that occured at the iteration
    equal to the last iteration on disk plus the ``thinned_by`` interval.
    If this iteration is larger than the iteration of the last given
    sample, then none of the samples will be written.

    Parameters
    -----------
    fp : BaseInferenceFile
        Open file handler to write files to. Must be an instance of
        BaseInferenceFile with CommonMCMCMetadataIO methods added.
    samples : dict
        The samples to write. Each array in the dictionary should have
        shape nwalkers x niterations.
    parameters : list, optional
        Only write the specified parameters to the file. If None, will
        write all of the keys in the ``samples`` dict.
    last_iteration : int, optional
        The iteration of the last sample. If the file's ``thinned_by``
        attribute is > 1, this is needed to determine where to start
        thinning the samples such that the interval between the last sample
        currently on disk and the first new sample is the same as all of
        the other samples.
    samples_group : str, optional
        Which group to write the samples to. Default (None) will result
        in writing to "samples".
    thin_by : int, optional
        Override the ``thinned_by`` attribute in the file with the given
        value. **Only set this if you are using this function to write
        something other than inference samples!**
    """
    nwalkers, nsamples = list(samples.values())[0].shape
    assert all(p.shape == (nwalkers, nsamples)
               for p in samples.values()), (
           "all samples must have the same shape")
    if samples_group is None:
        samples_group = fp.samples_group
    if parameters is None:
        parameters = samples.keys()
    # thin the samples
    samples = thin_samples_for_writing(fp, samples, parameters,
                                       last_iteration, samples_group,
                                       thin_by=thin_by)
    # loop over number of dimensions
    group = samples_group + '/{name}'
    for param in parameters:
        dataset_name = group.format(name=param)
        data = samples[param]
        # check that there's something to write after thinning
        if data.shape[1] == 0:
            # nothing to write, move along
            continue
        try:
            fp_nsamples = fp[dataset_name].shape[-1]
            istart = fp_nsamples
            istop = istart + data.shape[1]
            if istop > fp_nsamples:
                # resize the dataset
                fp[dataset_name].resize(istop, axis=1)
        except KeyError:
            # dataset doesn't exist yet
            istart = 0
            istop = istart + data.shape[1]
            fp.create_dataset(dataset_name, (nwalkers, istop),
                              maxshape=(nwalkers, None),
                              dtype=data.dtype,
                              fletcher32=True)
        fp[dataset_name][:, istart:istop] = data


def ensemble_read_raw_samples(fp, fields, thin_start=None,
                              thin_interval=None, thin_end=None,
                              iteration=None, walkers=None, flatten=True,
                              group=None):
    """Base function for reading samples from ensemble MCMC files without
    parallel tempering.

    Parameters
    -----------
    fp : BaseInferenceFile
        Open file handler to write files to. Must be an instance of
        BaseInferenceFile with EnsembleMCMCMetadataIO methods added.
    fields : list
        The list of field names to retrieve.
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
    walkers : (list of) int, optional
        Only read from the given walkers. Default (``None``) is to read all.
    flatten : bool, optional
        Flatten the samples to 1D arrays before returning. Otherwise, the
        returned arrays will have shape (requested walkers x
        requested iteration(s)). Default is True.
    group : str, optional
        The name of the group to read sample datasets from. Default is
        the file's ``samples_group``.

    Returns
    -------
    dict
        A dictionary of field name -> numpy array pairs.
    """
    if isinstance(fields, string_types):
        fields = [fields]
    # walkers to load
    widx, nwalkers = _ensemble_get_walker_index(fp, walkers)
    # get the slice to use
    get_index = _ensemble_get_index(fp, thin_start, thin_interval, thin_end,
                                    iteration)
    # load
    if group is None:
        group = fp.samples_group
    group = group + '/{name}'
    arrays = {}
    for name in fields:
        arr = fp[group.format(name=name)][widx, get_index]
        niterations = arr.shape[-1] if iteration is None else 1
        if flatten:
            arr = arr.flatten()
        else:
            # ensure that the returned array is 2D
            arr = arr.reshape((nwalkers, niterations))
        arrays[name] = arr
    return arrays


def _ensemble_get_walker_index(fp, walkers=None):
    """Convenience function to determine which walkers to load.

    Parameters
    ----------
    fp : BaseInferenceFile
        Open file handler to write files to. Must be an instance of
        BaseInferenceFile with EnsembleMCMCMetadataIO methods added.
    walkers : (list of) int, optional
        Only read from the given walkers. Default (``None``) is to read all.

    Returns
    -------
    widx : array or slice
        The walker indices to load.
    nwalkers : int
        The number of walkers that will be loaded.
    """
    if walkers is not None:
        widx = numpy.zeros(fp.nwalkers, dtype=bool)
        widx[walkers] = True
        nwalkers = widx.sum()
    else:
        widx = slice(None, None)
        nwalkers = fp.nwalkers
    return widx, nwalkers


def _ensemble_get_index(fp, thin_start=None, thin_interval=None, thin_end=None,
                        iteration=None):
    """Determines the sample indices to retrieve for an ensemble MCMC.

    Parameters
    -----------
    fp : BaseInferenceFile
        Open file handler to write files to. Must be an instance of
        BaseInferenceFile with EnsembleMCMCMetadataIO methods added.
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

    Returns
    -------
    slice or int
        The indices to retrieve.
    """
    if iteration is not None:
        get_index = int(iteration)
    else:
        if thin_start is None:
            thin_start = fp.thin_start
        if thin_interval is None:
            thin_interval = fp.thin_interval
        if thin_end is None:
            thin_end = fp.thin_end
        get_index = fp.get_slice(thin_start=thin_start,
                                 thin_interval=thin_interval,
                                 thin_end=thin_end)
    return get_index


def _get_index(fp, chains, thin_start=None, thin_interval=None, thin_end=None,
               iteration=None):
    """Determines the sample indices to retrieve for an MCMC with independent
    chains.

    Parameters
    -----------
    fp : BaseInferenceFile
        Open file handler to write files to. Must be an instance of
        BaseInferenceFile with EnsembleMCMCMetadataIO methods added.
    chains : array of int
        The chains to load.
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

    Returns
    -------
    get_index : list of slice or int
        The indices to retrieve.
    maxiters : int
        The maximum number of samples from a single chain that will be
        retrieved.
    """
    nchains = len(chains)
    if iteration is not None:
        maxiters = 1
        get_index = [int(iteration)]*nchains
    else:
        if thin_start is None:
            thin_start = fp.thin_start
        if not isinstance(thin_start, (numpy.ndarray, list)):
            thin_start = numpy.repeat(thin_start, nchains)
        if thin_interval is None:
            thin_interval = fp.thin_interval
        if not isinstance(thin_interval, (numpy.ndarray, list)):
            thin_interval = numpy.repeat(thin_interval, nchains)
        if thin_end is None:
            thin_end = fp.thin_end
        if not isinstance(thin_end, (numpy.ndarray, list)):
            thin_end = numpy.repeat(thin_end, nchains)
        # figure out the maximum number of samples we will get from all chains
        start_iter = thin_start * fp.thinned_by
        iter_interval = thin_interval * fp.thinned_by
        try:
            end_iter = thin_end * fp.thinned_by
        except TypeError:
            # will get this if thin end is None; in that case, we'll just be
            # loading all the way to the end
            end_iter = fp.niterations
        maxiters = nsamples_in_chain(start_iter, iter_interval, end_iter).max()
        # the slices to use for each chain
        get_index = [fp.get_slice(thin_start=thin_start[ci],
                                  thin_interval=thin_interval[ci],
                                  thin_end=thin_end[ci])
                     for ci in chains]
    return get_index, maxiters


def thin_samples_for_writing(fp, samples, parameters, last_iteration,
                             group, thin_by=None):
    """Thins samples for writing to disk.

    The thinning interval to use is determined by the given file handler's
    ``thinned_by`` attribute. If that attribute is 1, just returns the samples.

    Parameters
    ----------
    fp : CommonMCMCMetadataIO instance
        The file the sampels will be written to. Needed to determine the
        thin interval used on disk.
    samples : dict
        Dictionary mapping parameter names to arrays of (unthinned) samples.
        The arrays are thinned along their last dimension.
    parameters : list of str
        The parameters to thin in ``samples`` before writing. All listed
        parameters must be in ``samples``.
    last_iteration : int
        The iteration that the last sample in ``samples`` occurred at. This is
        needed to figure out where to start the thinning in ``samples``, such
        that the interval between the last sample on disk and the first new
        sample is the same as all of the other samples.
    group : str
        The name of the group that the samples will be written to. This is
        needed to determine what the last iteration saved on disk was.
    thin_by : int, optional
        Override the ``thinned_by`` attribute in the file for with the given
        value. **Only do this if you are thinning something other than
        inference samples!**

    Returns
    -------
    dict :
        Dictionary of the thinned samples to write.
    """
    if thin_by is None:
        thin_by = fp.thinned_by
    if thin_by > 1:
        if last_iteration is None:
            raise ValueError("File's thinned_by attribute is > 1 ({}), "
                             "but last_iteration not provided."
                             .format(thin_by))
        thinned_samples = {}
        for param in parameters:
            data = samples[param]
            nsamples = data.shape[-1]
            # To figure out where to start:
            # the last iteration in the file + the file's thinning interval
            # gives the iteration of the next sample that should be written;
            # last_iteration - nsamples gives the iteration of the first
            # sample in samples. Subtracting the latter from the former - 1
            # (-1 to convert from iteration to index) therefore gives the index
            # in the samples data to start using samples.
            thin_start = fp.last_iteration(param, group) + thin_by \
                - (last_iteration - nsamples) - 1
            thinned_samples[param] = data[..., thin_start::thin_by]
    else:
        thinned_samples = samples
    return thinned_samples


def nsamples_in_chain(start_iter, interval, niterations):
    """Calculates the number of samples in an MCMC chain given a thinning
    start, end, and interval.

    This function will work with either python scalars, or numpy arrays.

    Parameters
    ----------
    start_iter : (array of) int
        Start iteration. If negative, will count as being how many iterations
        to start before the end; otherwise, counts how many iterations to
        start before the beginning. If this is larger than niterations, will
        just return 0.
    interval : (array of) int
        Thinning interval.
    niterations : (array of) int
        The number of iterations.

    Returns
    -------
    numpy.int_
        The number of samples in a chain, >= 0.
    """
    # this is written in a slightly wonky way so that it will work with either
    # python scalars or numpy arrays; it is equivalent to:
    #    if start_iter < 0:
    #        count = min(abs(start_iter), niterations)
    #    else:
    #        count = max(niterations - start_iter, 0)
    slt0 = start_iter < 0
    sgt0 = start_iter >= 0
    count = slt0*abs(start_iter) + sgt0*(niterations - start_iter)
    # ensure count is in [0, niterations]
    cgtn = count > niterations
    cok = (count >= 0) & (count <= niterations)
    count = cgtn*niterations + cok*count
    return numpy.ceil(count / interval).astype(int)
