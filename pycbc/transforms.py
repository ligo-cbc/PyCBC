# Copyright (C) 2017  Christopher M. Biwer
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
This modules provides classes and functions for transforming parameters.
"""

import copy
import logging
import numpy
from pycbc import conversions
from pycbc import coordinates
from pycbc import cosmology
from pycbc.io import record
from pycbc.waveform import parameters

class BaseTransform(object):
    """A base class for transforming between two sets of parameters.
    """
    name = None
    inverse = None
    _inputs = []
    _outputs = []

    def __init__(self):
        self.inputs = set(self._inputs)
        self.outputs = set(self._outputs)

    def transform(self, maps):
        """ This function transforms from inputs to outputs.
        """
        raise NotImplementedError("Not added.")

    def inverse_transform(self, maps):
        """ The inverse conversions of transform. This function transforms from
        outputs to inputs.
        """
        raise NotImplementedError("Not added.")

    def jacobian(self, maps):
        """ The Jacobian for the inputs to outputs transformation.
        """
        raise NotImplementedError("Jacobian transform not implemented.")

    def inverse_jacobian(self, maps):
        """ The Jacobian for the outputs to inputs transformation.
        """
        raise NotImplementedError("Jacobian transform not implemented.")

    @staticmethod
    def format_output(old_maps, new_maps):
        """ This function takes the returned dict from `transform` and converts
        it to the same datatype as the input.

        Parameters
        ----------
        old_maps : {FieldArray, dict}
            The mapping object to add new maps to.
        new_maps : dict
            A dict with key as parameter name and value is numpy.array.

        Returns
        -------
        {FieldArray, dict}
            The old_maps object with new keys from new_maps.
        """

        # if input is FieldArray then return FieldArray
        if isinstance(old_maps, record.FieldArray):
            keys = new_maps.keys()
            values = [new_maps[key] for key in keys]
            for key, vals in zip(keys, values):
                try:
                    old_maps = old_maps.add_fields([vals], [key])
                except ValueError:
                    old_maps[key] = vals
            return old_maps

        # if input is dict then return dict
        elif isinstance(old_maps, dict):
            out = old_maps.copy()
            out.update(new_maps)
            return out

        # else error
        else:
            raise TypeError("Input type must be FieldArray or dict.")


#
# =============================================================================
#
#                             Forward Transforms
#
# =============================================================================
#

class MchirpQToMass1Mass2(BaseTransform):
    """ Converts chirp mass and mass ratio to component masses.
    """
    name = "mchirp_q_to_mass1_mass2"
    _inputs = [parameters.mchirp, parameters.q]
    _outputs = [parameters.mass1, parameters.mass2]

    def transform(self, maps):
        """This function transforms from chirp mass and mass ratio to component
        masses.

        Parameters
        ----------
        maps : a mapping object

        Examples
        --------
        Convert a dict of numpy.array:

        >>> import numpy
        >>> from pycbc import transforms
        >>> t = transforms.MchirpQToMass1Mass2()
        >>> t.transform({'mchirp': numpy.array([10.]), 'q': numpy.array([2.])})
        {'mass1': array([ 16.4375183]), 'mass2': array([ 8.21875915]),
         'mchirp': array([ 10.]), 'q': array([ 2.])}

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {}
        out[parameters.mass1] = conversions.mass1_from_mchirp_q(
                                                maps[parameters.mchirp],
                                                maps[parameters.q])
        out[parameters.mass2] = conversions.mass2_from_mchirp_q(
                                                maps[parameters.mchirp],
                                                maps[parameters.q])
        return self.format_output(maps, out)

    def inverse_transform(self, maps):
        """This function transforms from component masses to chirp mass and
        mass ratio.

        Parameters
        ----------
        maps : a mapping object

        Examples
        --------
        Convert a dict of numpy.array:

        >>> import numpy
        >>> from pycbc import transforms
        >>> t = transforms.MchirpQToMass1Mass2()
        >>> t.inverse_transform({'mass1': numpy.array([16.4]), 'mass2': numpy.array([8.2])})
            {'mass1': array([ 16.4]), 'mass2': array([ 8.2]),
             'mchirp': array([ 9.97717521]), 'q': 2.0}

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {}
        out[parameters.mchirp] = \
                 conversions.mchirp_from_mass1_mass2(maps[parameters.mass1],
                                                     maps[parameters.mass2])
        m_p = conversions.primary_mass(maps[parameters.mass1],
                                       maps[parameters.mass2])
        m_s = conversions.secondary_mass(maps[parameters.mass1],
                                         maps[parameters.mass2])
        out[parameters.q] = m_p / m_s
        return self.format_output(maps, out)

    def jacobian(self, maps):
        """ Returns the Jacobian from chirp mass and mass ratio to
        component masses.
        """
        tmp = self.transform(maps)
        return maps["mchirp"] / tmp["mass2"]**2


class SphericalSpin1ToCartesianSpin1(BaseTransform):
    """ Converts spherical spin parameters (magnitude and two angles) to
    catesian spin parameters. This class only transforms spsins for the first
    component mass.
    """
    name = "spherical_spin_1_to_cartesian_spin_1"
    _inputs = [parameters.spin1_a, parameters.spin1_azimuthal,
               parameters.spin1_polar]
    _outputs = [parameters.spin1x, parameters.spin1y, parameters.spin1z]

    def transform(self, maps):
        """ This function transforms from spherical to cartesian spins.

        Parameters
        ----------
        maps : a mapping object

        Examples
        --------
        Convert a dict of numpy.array:

        >>> import numpy
        >>> from pycbc import transforms
        >>> t = transforms.SphericalSpin1ToCartesianSpin1()
        >>> t.transform({'spin1_a': numpy.array([0.1]), 'spin1_azimuthal': numpy.array([0.1]), 'spin1_polar': numpy.array([0.1])})
            {'spin1_a': array([ 0.1]), 'spin1_azimuthal': array([ 0.1]), 'spin1_polar': array([ 0.1]),
             'spin2x': array([ 0.00993347]), 'spin2y': array([ 0.00099667]), 'spin2z': array([ 0.09950042])}

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        a, az, po = self._inputs
        data = coordinates.spherical_to_cartesian(maps[a], maps[az], maps[po])
        out = {param : val for param, val in zip(self._outputs, data)}
        return self.format_output(maps, out)

    def inverse_transform(self, maps):
        """ This function transforms from cartesian to spherical spins.

        Parameters
        ----------
        maps : a mapping object

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        sx, sy, sz = self._outputs
        data = coordinates.cartesian_to_spherical(maps[sx], maps[sy], maps[sz])
        out = {param : val for param, val in zip(self._outputs, data)}
        return self.format_output(maps, out)


class SphericalSpin2ToCartesianSpin2(SphericalSpin1ToCartesianSpin1):
    """ Converts spherical spin parameters (magnitude and two angles) to
    catesian spin parameters. This class only transforms spsins for the second
    component mass.
    """
    name = "spherical_spin_2_to_cartesian_spin_2"
    _inputs = [parameters.spin2_a, parameters.spin2_azimuthal,
               parameters.spin2_polar]
    _outputs = [parameters.spin2x, parameters.spin2y, parameters.spin2z]


class DistanceToRedshift(BaseTransform):
    """ Converts distance to redshift.
    """
    name = "distance_to_redshift"
    inverse = None
    _inputs = [parameters.distance]
    _outputs = [parameters.redshift]

    def transform(self, maps):
        """ This function transforms from distance to redshift.

        Parameters
        ----------
        maps : a mapping object

        Examples
        --------
        Convert a dict of numpy.array:

        >>> import numpy
        >>> from pycbc import transforms
        >>> t = transforms.DistanceToRedshift()
        >>> t.transform({'distance': numpy.array([1000])})
            {'distance': array([1000]), 'redshift': 0.19650987609144363}

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {parameters.redshift : cosmology.redshift(
                                                    maps[parameters.distance])}
        return self.format_output(maps, out)


class AlignedMassSpinToCartesianSpin(BaseTransform):
    """ Converts mass-weighted spins to cartesian z-axis spins.
    """
    name = "aligned_mass_spin_to_cartesian_spin"
    _inputs = [parameters.mass1, parameters.mass2, parameters.chi_eff, "chi_a"]
    _outputs = [parameters.mass1, parameters.mass2,
               parameters.spin1z, parameters.spin2z]

    def transform(self, maps):
        """ This function transforms from aligned mass-weighted spins to
        cartesian spins aligned along the z-axis.

        Parameters
        ----------
        maps : a mapping object

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {}
        out[parameters.spin1z] = \
                         conversions.spin1z_from_mass1_mass2_chi_eff_chi_a(
                               maps[parameters.mass1], maps[parameters.mass2],
                               maps[parameters.chi_eff], maps["chi_a"])

        out[parameters.spin2z] = \
                         conversions.spin2z_from_mass1_mass2_chi_eff_chi_a(
                               maps[parameters.mass1], maps[parameters.mass2],
                               maps[parameters.chi_eff], maps["chi_a"])
        return self.format_output(maps, out)

    def inverse_transform(self, maps):
        """ This function transforms from component masses and cartesian spins to
        mass-weighted spin parameters aligned with the angular momentum.

        Parameters
        ----------
        maps : a mapping object

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {
            parameters.chi_eff : conversions.chi_eff(
                             maps[parameters.mass1], maps[parameters.mass2],
                             maps[parameters.spin1z], maps[parameters.spin2z]),
            "chi_a" : conversions.chi_a(
                             maps[parameters.mass1], maps[parameters.mass2],
                             maps[parameters.spin1z], maps[parameters.spin2z]),
        }
        return self.format_output(maps, out)


class PrecessionMassSpinToCartesianSpin(BaseTransform):
    """ Converts mass-weighted spins to cartesian x-y plane spins.
    """
    name = "precession_mass_spin_to_cartesian_spin"
    _inputs = [parameters.mass1, parameters.mass2,
               "xi1", "xi2", "phi_a", "phi_s"]
    _outputs = [parameters.mass1, parameters.mass2,
                parameters.spin1x, parameters.spin1y,
                parameters.spin2x, parameters.spin2y]

    def transform(self, maps):
        """ This function transforms from mass-weighted spins to caretsian spins
        in the x-y plane.

        Parameters
        ----------
        maps : a mapping object

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {}
        out[parameters.spin1x] = conversions.spin1x_from_xi1_phi_a_phi_s(
                               maps["xi1"], maps["phi_a"], maps["phi_s"])
        out[parameters.spin1y] = conversions.spin1y_from_xi1_phi_a_phi_s(
                               maps["xi1"], maps["phi_a"], maps["phi_s"])
        out[parameters.spin2x] = \
                         conversions.spin2x_from_mass1_mass2_xi2_phi_a_phi_s(
                               maps[parameters.mass1], maps[parameters.mass2],
                               maps["xi2"], maps["phi_a"], maps["phi_s"])
        out[parameters.spin2y] = \
                         conversions.spin2y_from_mass1_mass2_xi2_phi_a_phi_s(
                               maps[parameters.mass1], maps[parameters.mass2],
                               maps["xi2"], maps["phi_a"], maps["phi_s"])
        return self.format_output(maps, out)

    def inverse_transform(self, maps):
        """ This function transforms from component masses and cartesian spins to
        mass-weighted spin parameters perpendicular with the angular momentum.

        Parameters
        ----------
        maps : a mapping object

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {}
        out["xi1"] = conversions.primary_xi(
                             maps[parameters.mass1], maps[parameters.mass2],
                             maps[parameters.spin1x], maps[parameters.spin1y],
                             maps[parameters.spin2x], maps[parameters.spin2y])
        out["xi2"] = conversions.secondary_xi(
                             maps[parameters.mass1], maps[parameters.mass2],
                             maps[parameters.spin1x], maps[parameters.spin1y],
                             maps[parameters.spin2x], maps[parameters.spin2y])
        out["phi_a"] = conversions.phi_a(
                             maps[parameters.spin1x], maps[parameters.spin1y],
                             maps[parameters.spin2x], maps[parameters.spin2y])
        out["phi_s"] = conversions.phi_s(
                             maps[parameters.spin1x], maps[parameters.spin1y],
                             maps[parameters.spin2x], maps[parameters.spin2y])
        return self.format_output(maps, out)


class ChiPToCartesianSpin(BaseTransform):
    """Converts chi_p to cartesian spins.
    """
    name = "chi_p_to_cartesian_spin"
    _inputs = ["chi_p"]
    _outputs = [parameters.mass1, parameters.mass2,
                parameters.spin1x, parameters.spin1y,
                parameters.spin2x, parameters.spin2y]

    def inverse_transform(self, maps):
        """ This function transforms from component masses and caretsian spins
        to chi_p.

        Parameters
        ----------
        maps : a mapping object

        Examples
        --------
        Convert a dict of numpy.array:

        >>> import numpy
        >>> from pycbc import transforms
        >>> from pycbc.waveform import parameters
        >>> cl = transforms.DistanceToRedshift()
        >>> cl.transform({parameters.distance : numpy.array([1000])})
            {'distance': array([1000]), 'redshift': 0.19650987609144363}

        Returns
        -------
        out : dict
            A dict with key as parameter name and value as numpy.array or float
            of transformed values.
        """
        out = {}
        out["chi_p"] = conversions.chi_p(
                             maps[parameters.mass1], maps[parameters.mass2],
                             maps[parameters.spin1x], maps[parameters.spin1y],
                             maps[parameters.spin2x], maps[parameters.spin2y])
        return self.format_output(maps, out)


#
# =============================================================================
#
#                             Inverse Transforms
#
# =============================================================================
#
class Mass1Mass2ToMchirpQ(MchirpQToMass1Mass2):
    """The inverse of MchirpQToMass1Mass2.
    """
    name = "mass1_mass2_to_mchirp_q"
    inverse = MchirpQToMass1Mass2
    _inputs = inverse._outputs
    _outputs = inverse._inputs
    transform = inverse.inverse_transform
    inverse_transform = inverse.transform
    jacobian = inverse.inverse_jacobian
    inverse_jacobian = inverse.jacobian


class CartesianSpin1ToSphericalSpin1(SphericalSpin1ToCartesianSpin1):
    """The inverse of SphericalSpin1ToCartesianSpin1.
    """
    name = "cartesian_spin_1_to_spherical_spin_1"
    inverse = SphericalSpin1ToCartesianSpin1
    _inputs = inverse._outputs
    _outputs = inverse._inputs
    transform = inverse.inverse_transform
    inverse_transform = inverse.transform
    jacobian = inverse.inverse_jacobian
    inverse_jacobian = inverse.jacobian


class CartesianSpin2ToSphericalSpin2(SphericalSpin2ToCartesianSpin2):
    """The inverse of SphericalSpin2ToCartesianSpin2.
    """
    name = "cartesian_spin_2_to_spherical_spin_2"
    inverse = SphericalSpin2ToCartesianSpin2
    _inputs = inverse._outputs
    _outputs = inverse._inputs
    transform = inverse.inverse_transform
    inverse_transform = inverse.transform
    jacobian = inverse.inverse_jacobian
    inverse_jacobian = inverse.jacobian


class CartesianSpinToAlignedMassSpin(AlignedMassSpinToCartesianSpin):
    """The inverse of AlignedMassSpinToCartesianSpin."""
    name = "cartesian_spin_to_aligned_mass_spin"
    inverse = AlignedMassSpinToCartesianSpin
    _inputs = inverse._outputs
    _outputs = inverse._inputs
    transform = inverse.inverse_transform
    inverse_transform = inverse.transform
    jacobian = inverse.inverse_jacobian
    inverse_jacobian = inverse.jacobian


class CartesianSpinToPrecessionMassSpin(PrecessionMassSpinToCartesianSpin):
    """The inverse of PrecessionMassSpinToCartesianSpin.
    """
    name = "cartesian_spin_to_precession_mass_spin"
    inverse = PrecessionMassSpinToCartesianSpin
    _inputs = inverse._outputs
    _outputs = inverse._inputs
    transform = inverse.inverse_transform
    inverse_transform = inverse.transform
    jacobian = inverse.inverse_jacobian
    inverse_jacobian = inverse.jacobian


class CartesianSpinToChiP(ChiPToCartesianSpin):
    """The inverse of ChiPToCartesianSpin.
    """
    name = "cartesian_spin_to_chi_p"
    inverse = ChiPToCartesianSpin
    _inputs = inverse._outputs
    _outputs = inverse._inputs
    transform = inverse.inverse_transform
    inverse_transform = inverse.transform
    jacobian = inverse.inverse_jacobian
    inverse_jacobian = inverse.jacobian


# set the inverse of the forward transforms to the inverse transforms
MchirpQToMass1Mass2.inverse = Mass1Mass2ToMchirpQ
SphericalSpin1ToCartesianSpin1.inverse = CartesianSpin1ToSphericalSpin1
SphericalSpin2ToCartesianSpin2.inverse = CartesianSpin2ToSphericalSpin2
AlignedMassSpinToCartesianSpin.inverse = CartesianSpinToAlignedMassSpin
PrecessionMassSpinToCartesianSpin.inverse = CartesianSpinToPrecessionMassSpin
ChiPToCartesianSpin.inverse = CartesianSpinToChiP


#
# =============================================================================
#
#                      Collections of transforms
#
# =============================================================================
#

# dictionary of all transforms
transforms = {
    MchirpQToMass1Mass2.name : MchirpQToMass1Mass2,
    Mass1Mass2ToMchirpQ.name : Mass1Mass2ToMchirpQ,
    SphericalSpin1ToCartesianSpin1.name : SphericalSpin1ToCartesianSpin1,
    CartesianSpin1ToSphericalSpin1.name : CartesianSpin1ToSphericalSpin1,
    SphericalSpin2ToCartesianSpin2.name : SphericalSpin2ToCartesianSpin2,
    CartesianSpin2ToSphericalSpin2.name : CartesianSpin2ToSphericalSpin2,
    DistanceToRedshift.name : DistanceToRedshift,
    AlignedMassSpinToCartesianSpin.name : AlignedMassSpinToCartesianSpin,
    CartesianSpinToAlignedMassSpin.name : CartesianSpinToAlignedMassSpin,
    PrecessionMassSpinToCartesianSpin.name : PrecessionMassSpinToCartesianSpin,
    CartesianSpinToPrecessionMassSpin.name : CartesianSpinToPrecessionMassSpin,
    ChiPToCartesianSpin.name : ChiPToCartesianSpin,
    CartesianSpinToChiP.name : CartesianSpinToChiP,
}

# standard CBC transforms: these are transforms that do not require input
# arguments; they are typically used in CBC parameter estimation to transform
# to coordinates understood by the waveform generator
common_cbc_forward_transforms = [
    MchirpQToMass1Mass2(), DistanceToRedshift(),
    SphericalSpin1ToCartesianSpin1(), SphericalSpin2ToCartesianSpin2(),
    AlignedMassSpinToCartesianSpin(), PrecessionMassSpinToCartesianSpin(),
    ChiPToCartesianSpin(),
]
common_cbc_inverse_transforms = [_t.inverse()
                                   for _t in common_cbc_forward_transforms
                                   if _t.inverse is not None]
common_cbc_transforms = common_cbc_forward_transforms + \
                        common_cbc_inverse_transforms


def get_common_cbc_transforms(requested_params, variable_args,
                              valid_params=None):
    """Determines if any additional parameters from the InferenceFile are
    needed to get derived parameters that user has asked for.

    First it will try to add any base parameters that are required to calculate
    the derived parameters. Then it will add any sampling parameters that are
    required to calculate the base parameters needed.

    Parameters
    ----------
    requested_params : list
        List of parameters that user wants.
    variable_args : list
        List of parameters that InferenceFile has.
    valid_params : list
        List of parameters that can be accepted.

    Returns
    -------
    requested_params : list
        Updated list of parameters that user wants.
    all_c : list
        List of BaseTransforms to apply.
    """

    # try to parse any equations by putting all strings together
    # this will get some garbage but ensures all alphanumeric/underscored
    # parameter names are added
    new_params = []
    for opt in requested_params:
        s = ""
        for ch in opt:
            s += ch if ch.isalnum() or ch == "_" else " "
        eqn = opt.split(":")[0]
        new_params += s.split(" ")
    requested_params = set(requested_params + new_params)

    # can pass a list of valid parameters to remove garbage from parsing above
    if valid_params:
        valid_params = set(valid_params)
        requested_params = requested_params.intersection(valid_params)

    # find all the transforms for the requested derived parameters
    # calculated from base parameters
    from_base_c = []
    for converter in common_cbc_forward_transforms:
        if (converter.outputs.issubset(variable_args) or
                converter.outputs.isdisjoint(requested_params)):
            continue
        intersect = converter.outputs.intersection(requested_params)
        if len(intersect) < 1 or intersect.issubset(converter.inputs):
            continue
        requested_params.update(converter.inputs)
        from_base_c.append(converter)

    # find all the tranforms for the required base parameters
    # calculated from sampling parameters
    to_base_c = []
    for converter in common_cbc_inverse_transforms:
        if (converter.inputs.issubset(variable_args) and
                len(converter.outputs.intersection(requested_params)) > 0):
            requested_params.update(converter.inputs)
            to_base_c.append(converter)

    # get list of transforms that converts sampling parameters to the base
    # parameters and then converts base parameters to the derived parameters
    all_c = to_base_c + from_base_c

    return list(requested_params), all_c


def apply_transforms(samples, transforms):
    """Applies a list of BaseTransform instances on a mapping object.

    Parameters
    ----------
    samples : {FieldArray, dict}
        Mapping object to apply transforms to.
    transforms : list
        List of BaseTransform instances to apply.

    Returns
    -------
    samples : {FieldArray, dict}
        Mapping object with conversions applied. Same type as input.
    """
    for t in tranforms:
        try:
            samples = t.transform(samples)
        except NotImplementedError:
            continue
    return samples
