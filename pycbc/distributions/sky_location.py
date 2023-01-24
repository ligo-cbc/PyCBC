# Copyright (C) 2016  Collin Capano
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
"""This modules provides classes for evaluating sky distributions in
right acension and declination.
"""


import numpy
from pycbc.distributions import angular
from pycbc.transforms import new_z_to_euler, rotate_euler
from pycbc.transforms import decra2polaz, polaz2radec

class UniformSky(angular.UniformSolidAngle):
    """A distribution that is uniform on the sky. This is the same as
    UniformSolidAngle, except that the polar angle varies from pi/2 (the north
    pole) to -pi/2 (the south pole) instead of 0 to pi. Also, the default
    names are "dec" (declination) for the polar angle and "ra" (right
    ascension) for the azimuthal angle, instead of "theta" and "phi".
    """
    name = 'uniform_sky'
    _polardistcls = angular.CosAngle
    _default_polar_angle = 'dec'
    _default_azimuthal_angle = 'ra'

class Fisher():
    """A distribution that returns a random (ra, dec) angle drawn from the
    Fisher distribution. Assume that the concentration parameter (kappa)
    is large so that we can use a Rayleigh distribution about the north
    pole and rotate it to be centered at the (ra, dec) coordinate mu.

    Assume kappa = 1 / sigma**2 (kappa should be in units of steradians)

    As in UniformSky, the declination (dec) varies from pi/2 to-pi/2
    and right ascension (ra) varies from 0 to 2pi. And the angles
    should be provided in (ra,dec) format in radians (mu_radians=True),
    rather than factors of pi, or in degrees (mu_radians=False).

    References:
      * http://en.wikipedia.org/wiki/Von_Mises-Fisher_distribution
      * http://arxiv.org/pdf/0902.0737v1 (states the Rayleigh limit)
    """
    name = 'fisher'
    _polardistcls = angular.CosAngle
    _default_polar_angle = 'dec'
    _default_azimuthal_angle = 'ra'

    def __init__(self, mu_values, kappa, mu_radians=True):
        self.kappa = kappa
        if kappa >= 500:
            if mu_radians:
                self.mu_values = numpy.array(mu_values[0], mu_values[1])
            else:
                self.mu_values = numpy.array(numpy.deg2rad([mu_values[0],
                                                            mu_values[1]]))
            self.mu_values = decra2polaz(self.mu_values[1], self.mu_values[0])
        else:
            raise ValueError("Kappa too low, minimum should be 500")

    def rvs_polaz(self, size):
        """
        Randomly draw multiple samples from the Fisher distribution
        and returns (polar, azimuthal) angle values.
        """
        arr = numpy.array([
            numpy.random.rayleigh(scale=1./numpy.sqrt(self.kappa),
                                  size=size),
            numpy.random.uniform(low=0,
                                 high=2*numpy.pi,
                                 size=size)]).reshape((2, size)).T
        alpha, beta = new_z_to_euler(self.mu_values)
        return rotate_euler(arr, alpha, beta, 0)

    def rvs_radec(self, size):
        """
        Randomly draw multiple samples from the Fisher distribution
        and returns (ra, dec) values
        """
        rot_eu = self.rvs_polaz(size)
        ra_a = rot_eu[:, 1]
        dec_p = rot_eu[:, 0]
        right_ascension, declination = polaz2radec(dec_p, ra_a)
        return right_ascension, declination


__all__ = ['UniformSky', 'Fisher']
