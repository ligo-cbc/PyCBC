# Copyright (C) 2018  Collin Capano
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


"""
This package provides classes and functions for evaluating Bayesian statistics
assuming various noise models.
"""


from pkg_resources import iter_entry_points as _iter_entry_points
from .base import BaseModel
from .base_data import BaseDataModel
from .analytic import (TestEggbox, TestNormal, TestRosenbrock, TestVolcano,
                       TestPrior, TestPosterior)
from .gaussian_noise import GaussianNoise
from .marginalized_gaussian_noise import MarginalizedPhaseGaussianNoise
from .marginalized_gaussian_noise import MarginalizedPolarization
from .marginalized_gaussian_noise import MarginalizedHMPolPhase
from .brute_marg import BruteParallelGaussianMarginalize
from .gated_gaussian_noise import (GatedGaussianNoise, GatedGaussianMargPol)
from .single_template import SingleTemplate
from .relbin import Relative
from .hierarchical import HierarchicalModel


# Used to manage a model instance across multiple cores or MPI
_global_instance = None


def _call_global_model(*args, **kwds):
    """Private function for global model (needed for parallelization)."""
    return _global_instance(*args, **kwds)  # pylint:disable=not-callable


def _call_global_model_logprior(*args, **kwds):
    """Private function for a calling global's logprior.

    This is needed for samplers that use a separate function for the logprior,
    like ``emcee_pt``.
    """
    # pylint:disable=not-callable
    return _global_instance(*args, callstat='logprior', **kwds)


class CallModel(object):
    """Wrapper class for calling models from a sampler.

    This class can be called like a function, with the parameter values to
    evaluate provided as a list in the same order as the model's
    ``variable_params``. In that case, the model is updated with the provided
    parameters and then the ``callstat`` retrieved. If ``return_all_stats`` is
    set to ``True``, then all of the stats specified by the model's
    ``default_stats`` will be returned as a tuple, in addition to the stat
    value.

    The model's attributes are promoted to this class's namespace, so that any
    attribute and method of ``model`` may be called directly from this class.

    This class must be initalized prior to the creation of a ``Pool`` object.

    Parameters
    ----------
    model : Model instance
        The model to call.
    callstat : str
        The statistic to call.
    return_all_stats : bool, optional
        Whether or not to return all of the other statistics along with the
        ``callstat`` value.

    Examples
    --------
    Create a wrapper around an instance of the ``TestNormal`` model, with the
    ``callstat`` set to ``logposterior``:

    >>> from pycbc.inference.models import TestNormal, CallModel
    >>> model = TestNormal(['x', 'y'])
    >>> call_model = CallModel(model, 'logposterior')

    Now call on a set of parameter values:

    >>> call_model([0.1, -0.2])
    (-1.8628770664093453, (0.0, 0.0, -1.8628770664093453))

    Note that a tuple of all of the model's ``default_stats`` were returned in
    addition to the ``logposterior`` value. We can shut this off by toggling
    ``return_all_stats``:

    >>> call_model.return_all_stats = False
    >>> call_model([0.1, -0.2])
    -1.8628770664093453

    Attributes of the model can be called from the call model. For example:

    >>> call_model.variable_params
    ('x', 'y')

    """

    def __init__(self, model, callstat, return_all_stats=True):
        self.model = model
        self.callstat = callstat
        self.return_all_stats = return_all_stats

    def __getattr__(self, attr):
        """Adds the models attributes to self."""
        return getattr(self.model, attr)

    def __call__(self, param_values, callstat=None, return_all_stats=None):
        """Updates the model with the given parameter values, then calls the
        call function.

        Parameters
        ----------
        param_values : list of float
            The parameter values to test. Assumed to be in the same order as
            ``model.sampling_params``.
        callstat : str, optional
            Specify which statistic to call. Default is to call whatever self's
            ``callstat`` is set to.
        return_all_stats : bool, optional
            Whether or not to return all stats in addition to the ``callstat``
            value. Default is to use self's ``return_all_stats``.

        Returns
        -------
        stat : float
            The statistic returned by the ``callfunction``.
        all_stats : tuple, optional
            The values of all of the model's ``default_stats`` at the given
            param values. Any stat that has not be calculated is set to
            ``numpy.nan``. This is only returned if ``return_all_stats`` is
            set to ``True``.
        """
        if callstat is None:
            callstat = self.callstat
        if return_all_stats is None:
            return_all_stats = self.return_all_stats
        params = dict(zip(self.model.sampling_params, param_values))
        self.model.update(**params)
        val = getattr(self.model, callstat)
        if return_all_stats:
            return val, self.model.get_current_stats()
        else:
            return val


def read_from_config(cp, **kwargs):
    """Initializes a model from the given config file.

    The section must have a ``name`` argument. The name argument corresponds to
    the name of the class to initialize.

    Parameters
    ----------
    cp : WorkflowConfigParser
        Config file parser to read.
    \**kwargs :
        All other keyword arguments are passed to the ``from_config`` method
        of the class specified by the name argument.

    Returns
    -------
    cls
        The initialized model.
    """
    # use the name to get the distribution
    name = cp.get("model", "name")
    return get_model(name).from_config(cp, **kwargs)


_models = {_cls.name: _cls for _cls in (
    TestEggbox,
    TestNormal,
    TestRosenbrock,
    TestVolcano,
    TestPosterior,
    TestPrior,
    GaussianNoise,
    MarginalizedPhaseGaussianNoise,
    MarginalizedPolarization,
    MarginalizedHMPolPhase,
    BruteParallelGaussianMarginalize,
    GatedGaussianNoise,
    GatedGaussianMargPol,
    SingleTemplate,
    Relative,
    HierarchicalModel,
)}



def register_model(model, force=False):
    """Makes a custom model available to PyCBC.

    The provided model will be added to the dictionary of models that PyCBC
    knows about, using the model's ``name`` attribute. If the ``name`` is the
    same as a model that already exists in PyCBC, a :py:exc:`RuntimeError` will
    be raised unless the ``force`` option is set to ``True``.

    Parameters
    ----------
    model : pycbc.inference.models.base.BaseModel
        The model to use. The model should be a sub-class of
        :py:class:`BaseModel <pycbc.inference.models.base.BaseModel>` to ensure
        it has the correct API for use within ``pycbc_inference``.
    force : bool, optional
        Add the model even if its ``name`` attribute is the same as a model
        that is already in :py:data:`pycbc.inference.models.models`. Otherwise,
        a :py:exc:`RuntimeError` will be raised. Default is ``False``.
    """
    if model.name in _models and not force:
        raise RuntimeError("Cannot add model {}; the name is already in use."
                           .format(model.name))
    _models[model.name] = model


class _ModelManager:
    """Retrieve the dictionary of available models.

    The first time this is called, any plugin models that are available will be
    added to the dictionary before returning.

    Returns
    -------
    dict :
        Dictionary of model names -> models.
    """
    def __init__(self):
        self.retrieve_plugins = True

    def __call__(self):
        if self.retrieve_plugins:
            for plugin in _iter_entry_points('pycbc.inference.models'):
                register_model(plugin.resolve())
            self.retrieve_plugins = False
        return _models
        

get_models = _ModelManager()


def get_model(model_name):
    """Retrieve the given model.

    Parameters
    ----------
    model_name : str
        The name of the model to get.

    Returns
    -------
    model :
        The requested model.
    """
    return get_models()[model_name]


def available_models():
    """List the currently available models."""
    return list(get_models().keys())
