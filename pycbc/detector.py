# -*- coding: UTF-8 -*-

# Copyright (C) 2012  Alex Nitz
#
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
"""This module provides utilities for calculating detector responses and timing
between observatories.
"""
import os
import logging
import numpy as np
from numpy import cos, sin, pi

import lal
from astropy.time import Time
from astropy import constants, coordinates, units
from astropy.coordinates.matrix_utilities import rotation_matrix
from astropy.units.si import sday, meter

import pycbc.libutils
from pycbc.types import TimeSeries
from pycbc.types.config import InterpolatingConfigParser

logger = logging.getLogger('pycbc.detector')

# Response functions are modelled after those in lalsuite and as also
# presented in https://arxiv.org/pdf/gr-qc/0008066.pdf

def gmst_accurate(gps_time):
    gmst = Time(gps_time, format='gps', scale='utc',
                location=(0, 0)).sidereal_time('mean').rad
    return gmst

def get_available_detectors():
    """ List the available detectors """
    dets = list(_ground_detectors.keys())
    return dets

def get_available_lal_detectors():
    """Return list of detectors known in the currently sourced lalsuite.
    This function will query lalsuite about which detectors are known to
    lalsuite. Detectors are identified by a two character string e.g. 'K1',
    but also by a longer, and clearer name, e.g. KAGRA. This function returns
    both. As LAL doesn't really expose this functionality we have to make some
    assumptions about how this information is stored in LAL. Therefore while
    we hope this function will work correctly, it's possible it will need
    updating in the future. Better if lal would expose this information
    properly.
    """
    ld = lal.__dict__
    known_lal_names = [j for j in ld.keys() if "DETECTOR_PREFIX" in j]
    known_prefixes = [ld[k] for k in known_lal_names]
    known_names = [ld[k.replace('PREFIX', 'NAME')] for k in known_lal_names]
    return list(zip(known_prefixes, known_names))

_ground_detectors = {}

def add_detector_on_earth(name, longitude, latitude,
                          yangle=0, xangle=None, height=0,
                          xlength=4000, ylength=4000,
                          xaltitude=0, yaltitude=0):
    """ Add a new detector on the earth

    Parameters
    ----------

    name: str
        two-letter name to identify the detector
    longitude: float
        Longitude in radians using geodetic coordinates of the detector
    latitude: float
        Latitude in radians using geodetic coordinates of the detector
    yangle: float
        Azimuthal angle of the y-arm (angle drawn from pointing north)
    xangle: float
        Azimuthal angle of the x-arm (angle drawn from point north). If not set
        we assume a right angle detector following the right-hand rule.
    xaltitude: float
        The altitude angle of the x-arm measured from the local horizon.
    yaltitude: float
        The altitude angle of the y-arm measured from the local horizon.
    height: float
        The height in meters of the detector above the standard
        reference ellipsoidal earth
    """
    if xangle is None:
        # assume right angle detector if no separate xarm direction given
        xangle = yangle + np.pi / 2.0

    # baseline response of a single arm pointed in the -X direction
    resp = np.array([[-1, 0, 0], [0, 0, 0], [0, 0, 0]])
    rm2 = rotation_matrix(-longitude * units.rad, 'z')
    rm1 = rotation_matrix(-1.0 * (np.pi / 2.0 - latitude) * units.rad, 'y')
    
    # Calculate response in earth centered coordinates
    # by rotation of response in coordinates aligned
    # with the detector arms
    resps = []
    vecs = []
    for angle, azi in [(yangle, yaltitude), (xangle, xaltitude)]:
        rm0 = rotation_matrix(angle * units.rad, 'z')
        rmN = rotation_matrix(-azi *  units.rad, 'y')
        rm = rm2 @ rm1 @ rm0 @ rmN
        # apply rotation
        resps.append(rm @ resp @ rm.T / 2.0)
        vecs.append(rm @ np.array([-1, 0, 0]))

    full_resp = (resps[0] - resps[1])
    loc = coordinates.EarthLocation.from_geodetic(longitude * units.rad,
                                                  latitude * units.rad,
                                                  height=height*units.meter)
    loc = np.array([loc.x.value, loc.y.value, loc.z.value])
    _ground_detectors[name] = {'location': loc,
                               'response': full_resp,
                               'xresp': resps[1],
                               'yresp': resps[0],
                               'xvec': vecs[1],
                               'yvec': vecs[0],
                               'yangle': yangle,
                               'xangle': xangle,
                               'height': height,
                               'xaltitude': xaltitude,
                               'yaltitude': yaltitude,
                               'ylength': ylength,
                               'xlength': xlength,
                              }

# Notation matches
# Eq 4 of https://link.aps.org/accepted/10.1103/PhysRevD.96.084004
def single_arm_frequency_response(f, n, arm_length):
    """ The relative amplitude factor of the arm response due to
    signal delay. This is relevant where the long-wavelength
    approximation no longer applies)
    """
    n = np.clip(n, -0.999, 0.999)
    phase = arm_length / constants.c.value * 2.0j * np.pi * f
    a = 1.0 / 4.0 / phase
    b = (1 - np.exp(-phase * (1 - n))) / (1 - n)
    c = np.exp(-2.0 * phase) * (1 - np.exp(phase * (1 + n))) / (1 + n)
    return a * (b - c) * 2.0  # We'll make this relative to the static resp

def load_detector_config(config_files):
    """ Add custom detectors from a configuration file

    Parameters
    ----------
    config_files: str or list of strs
        The config file(s) which specify new detectors
    """
    methods = {'earth_normal': (add_detector_on_earth,
                                ['longitude', 'latitude'])}
    conf = InterpolatingConfigParser(config_files)
    dets = conf.get_subsections('detector')
    for det in dets:
        kwds = dict(conf.items('detector-{}'.format(det)))
        try:
            method, arg_names = methods[kwds.pop('method')]
        except KeyError:
            raise ValueError("Missing or unkown method, "
                             "options are {}".format(methods.keys()))
        for k in kwds:
            kwds[k] = float(kwds[k])
        try:
            args = [kwds.pop(arg) for arg in arg_names]
        except KeyError as e:
            raise ValueError("missing required detector argument"
                             " {} are required".format(arg_names))
        method(det.upper(), *args, **kwds)


# prepopulate using detectors hardcoded into lalsuite
for pref, name in get_available_lal_detectors():
    lalsim = pycbc.libutils.import_optional('lalsimulation')
    lal_det = lalsim.DetectorPrefixToLALDetector(pref).frDetector
    add_detector_on_earth(pref,
                          lal_det.vertexLongitudeRadians,
                          lal_det.vertexLatitudeRadians,
                          height=lal_det.vertexElevation,
                          xangle=lal_det.xArmAzimuthRadians,
                          yangle=lal_det.yArmAzimuthRadians,
                          xlength=lal_det.xArmMidpoint * 2,
                          ylength=lal_det.yArmMidpoint * 2,
                          xaltitude=lal_det.xArmAltitudeRadians,
                          yaltitude=lal_det.yArmAltitudeRadians,
                          )

# autoload detector config files
if 'PYCBC_DETECTOR_CONFIG' in os.environ:
    load_detector_config(os.environ['PYCBC_DETECTOR_CONFIG'].split(':'))


class Detector(object):
    """A gravitational wave detector
    """
    def __init__(self, detector_name, reference_time=1126259462.0):
        """ Create class representing a gravitational-wave detector
        Parameters
        ----------
        detector_name: str
            The two-character detector string, i.e. H1, L1, V1, K1, I1
        reference_time: float
            Default is time of GW150914. In this case, the earth's rotation
        will be estimated from a reference time. If 'None', we will
        calculate the time for each gps time requested explicitly
        using a slower but higher precision method.
        """
        self.name = str(detector_name)
        
        lal_detectors = [pfx for pfx, name in get_available_lal_detectors()]
        if detector_name in _ground_detectors:
            self.info = _ground_detectors[detector_name]
            self.response = self.info['response']
            self.location = self.info['location']
        else:
            raise ValueError("Unkown detector {}".format(detector_name))

        loc = coordinates.EarthLocation(self.location[0],
                                        self.location[1],
                                        self.location[2],
                                        unit=meter)
        self.latitude = loc.lat.rad
        self.longitude = loc.lon.rad

        self.reference_time = reference_time
        self.sday = None
        self.gmst_reference = None

    def set_gmst_reference(self):
        if self.reference_time is not None:
            self.sday = float(sday.si.scale)
            self.gmst_reference = gmst_accurate(self.reference_time)
        else:
            raise RuntimeError("Can't get accurate sidereal time without GPS "
                               "reference time!")

    def lal(self):
        """ Return lal data type detector instance """
        import lal
        d = lal.FrDetector()
        d.vertexLongitudeRadians = self.longitude
        d.vertexLatitudeRadians = self.latitude
        d.vertexElevation = self.info['height']
        d.xArmAzimuthRadians = self.info['xangle']
        d.yArmAzimuthRadians = self.info['yangle']
        d.xArmAltitudeRadians = self.info['xaltitude']
        d.yArmAltitudeRadians = self.info['yaltitude']

        # This is somewhat abused by lalsimulation at the moment
        # to determine a filter kernel size. We set this only so that
        # value gets a similar number of samples as other detectors
        # it is used for nothing else
        d.yArmMidpoint = self.info['ylength'] / 2.0
        d.xArmMidpoint = self.info['xlength'] / 2.0

        x = lal.Detector()
        r = lal.CreateDetector(x, d, lal.LALDETECTORTYPE_IFODIFF)
        self._lal = r
        return r

    def gmst_estimate(self, gps_time):
        if self.reference_time is None:
            return gmst_accurate(gps_time)

        if self.gmst_reference is None:
            self.set_gmst_reference()
        dphase = (gps_time - self.reference_time) / self.sday * (2.0 * np.pi)
        gmst = (self.gmst_reference + dphase) % (2.0 * np.pi)
        return gmst

    def light_travel_time_to_detector(self, det):
        """ Return the light travel time from this detector
        Parameters
        ----------
        det: Detector
            The other detector to determine the light travel time to.
        Returns
        -------
        time: float
            The light travel time in seconds
        """
        d = self.location - det.location
        return float(d.dot(d)**0.5 / constants.c.value)

    def antenna_pattern(self, right_ascension, declination, polarization, t_gps,
                        frequency=0,
                        polarization_type='tensor'):
        """Return the detector response.

        Parameters
        ----------
        right_ascension: float or numpy.ndarray
            The right ascension of the source
        declination: float or numpy.ndarray
            The declination of the source
        polarization: float or numpy.ndarray
            The polarization angle of the source
        polarization_type: string flag: Tensor, Vector or Scalar
            The gravitational wave polarizations. Default: 'Tensor'

        Returns
        -------
        fplus(default) or fx or fb : float or numpy.ndarray
            The plus or vector-x or breathing polarization factor for this sky location / orientation
        fcross(default) or fy or fl : float or numpy.ndarray
            The cross or vector-y or longitudnal polarization factor for this sky location / orientation
        """
        if isinstance(t_gps, lal.LIGOTimeGPS):
            t_gps = float(t_gps)
        gha = self.gmst_estimate(t_gps) - right_ascension

        cosgha = cos(gha)
        singha = sin(gha)
        cosdec = cos(declination)
        sindec = sin(declination)
        cospsi = cos(polarization)
        sinpsi = sin(polarization)

        if frequency:
            e0 = cosdec * cosgha
            e1 = cosdec * -singha
            e2 = sin(declination)
            nhat = np.array([e0, e1, e2], dtype=object)

            nx = nhat.dot(self.info['xvec'])
            ny = nhat.dot(self.info['yvec'])

            rx = single_arm_frequency_response(frequency, nx,
                                               self.info['xlength'])
            ry = single_arm_frequency_response(frequency, ny,
                                               self.info['ylength'])
            resp = ry * self.info['yresp'] -  rx * self.info['xresp']
            ttype = np.complex128
        else:
            resp = self.response
            ttype = np.float64

        x0 = -cospsi * singha - sinpsi * cosgha * sindec
        x1 = -cospsi * cosgha + sinpsi * singha * sindec
        x2 =  sinpsi * cosdec

        x = np.array([x0, x1, x2], dtype=object)
        dx = resp.dot(x)

        y0 =  sinpsi * singha - cospsi * cosgha * sindec
        y1 =  sinpsi * cosgha + cospsi * singha * sindec
        y2 =  cospsi * cosdec

        y = np.array([y0, y1, y2], dtype=object)
        dy = resp.dot(y)

        if polarization_type != 'tensor':
            z0 = -cosdec * cosgha
            z1 = cosdec * singha
            z2 = -sindec
            z = np.array([z0, z1, z2], dtype=object)
            dz = resp.dot(z)

        if polarization_type == 'tensor':
            if hasattr(dx, 'shape'):
                fplus = (x * dx - y * dy).sum(axis=0).astype(ttype)
                fcross = (x * dy + y * dx).sum(axis=0).astype(ttype)
            else:
                fplus = (x * dx - y * dy).sum()
                fcross = (x * dy + y * dx).sum()
            return fplus, fcross

        elif polarization_type == 'vector':
            if hasattr(dx, 'shape'):
                fx = (z * dx + x * dz).sum(axis=0).astype(ttype)
                fy = (z * dy + y * dz).sum(axis=0).astype(ttype)
            else:
                fx = (z * dx + x * dz).sum()
                fy = (z * dy + y * dz).sum()

            return fx, fy

        elif polarization_type == 'scalar':
            if hasattr(dx, 'shape'):
                fb = (x * dx + y * dy).sum(axis=0).astype(ttype)
                fl = (z * dz).sum(axis=0)
            else:
                fb = (x * dx + y * dy).sum()
                fl = (z * dz).sum()
            return fb, fl

    def time_delay_from_earth_center(self, right_ascension, declination, t_gps):
        """Return the time delay from the earth center
        """
        return self.time_delay_from_location(np.array([0, 0, 0]),
                                             right_ascension,
                                             declination,
                                             t_gps)

    def time_delay_from_location(self, other_location, right_ascension,
                                 declination, t_gps):
        """Return the time delay from the given location to detector for
        a signal with the given sky location
        In other words return `t1 - t2` where `t1` is the
        arrival time in this detector and `t2` is the arrival time in the
        other location.

        Parameters
        ----------
        other_location : numpy.ndarray of coordinates
            A detector instance.
        right_ascension : float
            The right ascension (in rad) of the signal.
        declination : float
            The declination (in rad) of the signal.
        t_gps : float
            The GPS time (in s) of the signal.

        Returns
        -------
        float
            The arrival time difference between the detectors.
        """
        ra_angle = self.gmst_estimate(t_gps) - right_ascension
        cosd = cos(declination)

        e0 = cosd * cos(ra_angle)
        e1 = cosd * -sin(ra_angle)
        e2 = sin(declination)

        ehat = np.array([e0, e1, e2], dtype=object)
        dx = other_location - self.location
        return dx.dot(ehat).astype(np.float64) / constants.c.value

    def time_delay_from_detector(self, other_detector, right_ascension,
                                 declination, t_gps):
        """Return the time delay from the given to detector for a signal with
        the given sky location; i.e. return `t1 - t2` where `t1` is the
        arrival time in this detector and `t2` is the arrival time in the
        other detector. Note that this would return the same value as
        `time_delay_from_earth_center` if `other_detector` was geocentric.
        Parameters
        ----------
        other_detector : detector.Detector
            A detector instance.
        right_ascension : float
            The right ascension (in rad) of the signal.
        declination : float
            The declination (in rad) of the signal.
        t_gps : float
            The GPS time (in s) of the signal.
        Returns
        -------
        float
            The arrival time difference between the detectors.
        """
        return self.time_delay_from_location(other_detector.location,
                                             right_ascension,
                                             declination,
                                             t_gps)

    def project_wave(self, hp, hc, ra, dec, polarization,
                     method='lal',
                     reference_time=None):
        """Return the strain of a waveform as measured by the detector.
        Apply the time shift for the given detector relative to the assumed
        geocentric frame and apply the antenna patterns to the plus and cross
        polarizations.

        Parameters
        ----------
        hp: pycbc.types.TimeSeries
            Plus polarization of the GW
        hc: pycbc.types.TimeSeries
            Cross polarization of the GW
        ra: float
            Right ascension of source location
        dec: float
            Declination of source location
        polarization: float
            Polarization angle of the source
        method: {'lal', 'constant', 'vary_polarization'}
            The method to use for projecting the polarizations into the
            detector frame. Default is 'lal'.
        reference_time: float, Optional
            The time to use as, a reference for some methods of projection.
            Used by 'constant' and 'vary_polarization' methods. Uses average
            time if not provided.
        """
        # The robust and most fefature rich method which includes
        # time changing antenna patterns and doppler shifts due to the
        # earth rotation and orbit
        if method == 'lal':
            import lalsimulation
            h_lal = lalsimulation.SimDetectorStrainREAL8TimeSeries(
                    hp.astype(np.float64).lal(), hc.astype(np.float64).lal(),
                    ra, dec, polarization, self.lal())
            ts = TimeSeries(
                    h_lal.data.data, delta_t=h_lal.deltaT, epoch=h_lal.epoch,
                    dtype=np.float64, copy=False)

        # 'constant' assume fixed orientation relative to source over the
        # duration of the signal, accurate for short duration signals
        # 'fixed_polarization' applies only time changing orientation
        # but no doppler corrections
        elif method in ['constant', 'vary_polarization']:
            if reference_time is not None:
                rtime = reference_time
            else:
                # In many cases, one should set the reference time if using
                # this method as we don't know where the signal is within
                # the given time series. If not provided, we'll choose
                # the midpoint time.
                rtime = (float(hp.end_time) + float(hp.start_time)) / 2.0

            if method == 'constant':
                time = rtime
            elif method == 'vary_polarization':
                if (not isinstance(hp, TimeSeries) or
                   not isinstance(hc, TimeSeries)):
                    raise TypeError('Waveform polarizations must be given'
                                    ' as time series for this method')

                # this is more granular than needed, may be optimized later
                # assume earth rotation in ~30 ms needed for earth ceneter
                # to detector is completely negligible.
                time = hp.sample_times.numpy()

            fp, fc = self.antenna_pattern(ra, dec, polarization, time)
            dt = self.time_delay_from_earth_center(ra, dec, rtime)
            ts = fp * hp + fc * hc
            ts.start_time = float(ts.start_time) + dt

        # add in only the correction for the time variance in the polarization
        # due to the earth's rotation, no doppler correction applied
        else:
            raise ValueError("Unkown projection method {}".format(method))
        return ts

    def optimal_orientation(self, t_gps):
        """Return the optimal orientation in right ascension and declination
           for a given GPS time.

        Parameters
        ----------
        t_gps: float
            Time in gps seconds

        Returns
        -------
        ra: float
            Right ascension that is optimally oriented for the detector
        dec: float
            Declination that is optimally oriented for the detector
        """
        ra = self.longitude + (self.gmst_estimate(t_gps) % (2.0*np.pi))
        dec = self.latitude
        return ra, dec

    def get_icrs_pos(self):
        """ Transforms GCRS frame to ICRS frame

        Returns
        ----------
        loc: numpy.ndarray shape (3,1) units: AU
             ICRS coordinates in cartesian system
        """
        loc = self.location
        loc = coordinates.SkyCoord(x=loc[0], y=loc[1], z=loc[2], unit=units.m,
                frame='gcrs', representation_type='cartesian').transform_to('icrs')
        loc.representation_type = 'cartesian'
        conv = np.float32(((loc.x.unit/units.AU).decompose()).to_string())
        loc = np.array([np.float32(loc.x), np.float32(loc.y),
                        np.float32(loc.z)])*conv
        return loc

    def effective_distance(self, distance, ra, dec, pol, time, inclination):
        """ Distance scaled to account for amplitude factors

        The effective distance of the source. This scales the distance so that
        the amplitude is equal to a source which is optimally oriented with
        respect to the detector. For fixed detector-frame intrinsic parameters
        this is a measure of the expected signal strength.

        Parameters
        ----------
        distance: float
            Source luminosity distance in megaparsecs
        ra: float
            The right ascension in radians
        dec: float
            The declination in radians
        pol: float
            Polarization angle of the gravitational wave in radians
        time: float
            GPS time in seconds
        inclination:
            The inclination of the binary's orbital plane

        Returns
        -------
        eff_dist: float
            The effective distance of the source
        """
        fp, fc = self.antenna_pattern(ra, dec, pol, time)
        ic = np.cos(inclination)
        ip = 0.5 * (1. + ic * ic)
        scale = ((fp * ip) ** 2.0 + (fc * ic) ** 2.0) ** 0.5
        return distance / scale

def overhead_antenna_pattern(right_ascension, declination, polarization):
    """Return the antenna pattern factors F+ and Fx as a function of sky
    location and polarization angle for a hypothetical interferometer located
    at the north pole. Angles are in radians. Declinations of ±π/2 correspond
    to the normal to the detector plane (i.e. overhead and underneath) while
    the point with zero right ascension and declination is the direction
    of one of the interferometer arms.
    Parameters
    ----------
    right_ascension: float
    declination: float
    polarization: float
    Returns
    -------
    f_plus: float
    f_cros: float
    """
    # convert from declination coordinate to polar (angle dropped from north axis)
    theta = np.pi / 2.0 - declination

    f_plus  = - (1.0/2.0) * (1.0 + cos(theta)*cos(theta)) * \
                cos (2.0 * right_ascension) * cos (2.0 * polarization) - \
                cos(theta) * sin(2.0*right_ascension) * sin (2.0 * polarization)

    f_cross =   (1.0/2.0) * (1.0 + cos(theta)*cos(theta)) * \
                cos (2.0 * right_ascension) * sin (2.0* polarization) - \
                cos(theta) * sin(2.0*right_ascension) * cos (2.0 * polarization)

    return f_plus, f_cross


"""     LISA class      """

from pycbc.coordinates.space import ssb_to_lisa, TIME_OFFSET_20_DEGREES

try:
    import cupy
except ImportError:
    cupy = None

try:
    from lisatools.detector import ESAOrbits
except ImportError:
    ESAOrbits = None

try:
    from fastlisaresponse import pyResponseTDI
except ImportError:
    pyResponseTDI = None

class LISA_detector(object):
    """
    LISA-like GW detector. Applies detector response from FastLISAResponse.
    """
    def __init__(self, detector='LISA', reference_time=None, orbits=None,
                 use_gpu=False, apply_offset=False, offset=TIME_OFFSET_20_DEGREES):
        """
        Parameters
        ----------
        detector: str (optional)
            String specifying space-borne detector. Currently only accepts 'LISA',
            which is the default setting.

        reference_time: float (optional)
            The GPS start time of signal in the SSB frame. Default to start time of
            orbits input.

        orbits: lisatools.detector.Orbits (optional)
            Orbital information to pass into pyResponseTDI. Default
            lisatools.detector.ESAOrbits.

        use_gpu : bool (optional)
            Specify whether to run class on GPU support via CuPy. Default False.

        apply_offset : bool (optional)
            Specify whether to add a time offset to input times. If True,
            times are treated as GPS times, to which an offset is added to ensure
            LISA is ~20 degrees behind the Earth at t=0 (the LDC convention for the
            LISA start date). If False, no offset is applied. Default False.

        offset : float (optional)
            Time offset in seconds to apply to GPS times if apply_offset = True.
            Default pycbc.coordinates.space.TIME_OFFSET_20_DEGREES (places LISA
            ~20 deg behind Earth).
        """
        # initialize detector; for now we only accept LISA
        assert (detector=='LISA'), 'Currently only supports LISA detector'

        # intialize orbit information
        if orbits is None:
            # set ESAOrbits as default; raise error if ESAOrbits cannot be imported
            if ESAOrbits is None:
                raise ImportError('LISAanalysistools required for inputting orbital data')
            orbits = ESAOrbits()
        self.orbits = orbits
        orbit_start = self.orbits.t_base[0]
        orbit_end = self.orbits.t_base[-1]

        # specify whether to apply offsets to GPS times
        if apply_offset:
            self.offset = offset
        else:
            self.offset = 0.

        # specify and cache the start time
        if reference_time is None:
            self.ref_time = orbit_start + self.offset
        else:
            reference_time += self.offset
            assert (reference_time >= orbit_start) and (reference_time <= orbit_end), (
                    "Reference time is not in time domain of orbital data")
            self.ref_time = reference_time

        # allocate caches
        self.dt = None
        self.n = None
        self.pad_data = False # don't pad by default if only projecting
        self.sample_times = None
        self.response_init = None

        # initialize padding/cutting time length
        self.t0 = 10000.

        # initialize whether to use gpu; FLR handles if this cannot be done
        self.use_gpu = use_gpu

        # extrinsic params for LISA time conversion
        self.beta = None
        self.lamb = None
        self.pol = None

    def apply_polarization(self, hp, hc, polarization):
        """
        Apply polarization rotation matrix.

        Parameters
        ----------
        hp : array
            The plus polarization of the GW.

        hc : array
            The cross polarization of the GW.

        polarization : float
            The SSB polarization angle of the GW in radians.

        Returns
        -------
        (array, array)
            The plus and cross polarizations of the GW rotated by the polarization angle.
        """
        cphi = cos(2*polarization)
        sphi = sin(2*polarization)

        hp_ssb = hp*cphi - hc*sphi
        hc_ssb = hp*sphi + hc*cphi

        return hp_ssb, hc_ssb

    def get_links(self, hp, hc, lamb, beta, polarization=0, reference_time=None,
                  use_gpu=None):
        """
        Project a radiation frame waveform to the LISA constellation.

        Parameters
        ----------
        hp : pycbc.types.TimeSeries
            The plus polarization of the GW in the radiation frame.

        hc : pycbc.types.TimeSeries
            The cross polarization of the GW in the radiation frame.

        lamb : float
            The ecliptic longitude of the source in the SSB frame.

        beta : float
            The ecliptic latitude of the source in the SSB frame.

        polarization : float (optional)
            The polarization angle of the GW in radians. Default 0.

        reference_time : float (optional)
            The GPS start time of the GW signal in the SSB frame. Default to
            input on class initialization.

        use_gpu : bool (optional)
            Flag whether to use GPU support. Default to class input.
            CuPy is required if use_gpu is True; an ImportError will be raised
            if CuPy could not be imported.

        Returns
        -------
        ndarray
            The waveform projected to the LISA laser links.
        """
        if pyResponseTDI is None:
            raise ImportError('FastLISAResponse required for LISA projection/TDI')

        # get dt from waveform data
        if self.dt is None:
            self.dt = hp.delta_t

        # set waveform start time if specified
        if reference_time is not None:
            self.ref_time = reference_time + self.offset

        # specify and cache sample times
        start = self.ref_time
        base_dur = hp.duration
        if self.pad_data:
            start -= self.t0 # start should correspond to input signal, not pad
        hp.start_time = start
        hc.start_time = start
        self.sample_times = hp.sample_times.numpy()
        print('cached wf inputs and times')

        # make sure signal still lies within orbit length
        assert hp.duration + start <= self.orbits.t_base[-1], (
               "Time of signal end is greater than end of orbital data.")
        if self.pad_data:
            # specify that the padding is causing the issue
            assert start >= self.orbits.t_base[0], (
                   "Starting pad extends before start of orbital data. " + 
                   "Consider decreasing t0 or increasing reference time.")

        # configure the orbit to match signal
        self.orbits.configure(t_arr=self.sample_times)
        print('configured orbits')

        # rotate GW from radiation frame to SSB using polarization angle
        hp, hc = self.apply_polarization(hp, hc, polarization)
        print('applied polarization')

        # format wf to hp + i*hc
        hp = hp.numpy()
        hc = hc.numpy()
        wf = hp + 1j*hc
        print('converted to numpy')

        # save length of wf
        self.n = len(wf)

        # set use_gpu to class input if not specified
        if use_gpu is None:
            use_gpu = self.use_gpu

        # convert to cupy if needed
        if use_gpu:
            if cupy is None:
                raise ImportError('CuPy not imported but is required for GPU usage. ' +
                                  'Ensure use_gpu = False if not using GPU.')
            else:
                wf = cupy.asarray(wf)

        if self.response_init is None:
            # initialize the class
            print('fresh init')
            self.response_init = pyResponseTDI(1/self.dt, self.n, orbits=self.orbits,
                                               use_gpu=use_gpu)
        else:
            # update params in the initialized class
            print('update init')
            self.response_init.sampling_frequency = 1/self.dt
            self.response_init.num_pts = self.n
            self.response_init.orbits = self.orbits
            self.response_init.use_gpu = use_gpu
        print('response initialized')

        # project the signal
        self.response_init.get_projections(wf, lamb, beta, t0=self.t0)
        wf_proj = self.response_init.y_gw

        return wf_proj

    def project_wave(self, hp, hc, lamb, beta, polarization, reference_time=None,
                     tdi=2, tdi_chan='AET', tdi_orbits=None, use_gpu=None,
                     pad_data=False, remove_garbage=True, t0=None):
        """
        Evaluate the TDI observables.

        The TDI generation requires some startup time at the start and end of the
        waveform, creating erroneous ringing or "garbage" at the edges of the signal.
        By default, this method will cut off a time length t0 from the start and end
        to remove this garbage, which may delete sensitive data at the edges of the
        input data (e.g., the late inspiral and ringdown of a binary merger). Thus,
        the default output will be shorter than the input by (2*t0) seconds. See
        pad_data and remove_garbage to modify this behavior.

        Parameters
        ----------
        hp : pycbc.types.TimeSeries
            The plus polarization of the GW in the radiation frame.

        hc : pycbc.types.TimeSeries
            The cross polarization of the GW in the radiation frame.

        lamb : float
            The ecliptic longitude in the SSB frame.

        beta : float
            The ecliptic latitude in the SSB frame.

        polarization : float
            The polarization angle of the GW in radians.

        reference_time : float (optional)
            The GPS start time of the GW signal in the SSB frame. Default to
            value in input signals hp and hc.

        tdi : int (optional)
            TDI channel configuration. Accepts 1 for 1st generation TDI or
            2 for 2nd generation TDI. Default 2.

        tdi_chan : str (optional)
            The TDI observables to calculate. Accepts 'XYZ', 'AET', or 'AE'.
            Default 'AET'.

        tdi_orbits : lisatools.detector.Orbits (optional)
            Orbit keywords specifically for TDI generation. Default to class
            input.

        use_gpu : bool (optional)
            Flag whether to use GPU support. Default to class input.

        pad_data : bool (optional)
            Flag whether to pad the data with time length t0 of zeros at the
            start and end. If True, remove_garbage will interact with the
            pads rather than the input data. Default False.

        remove_garbage : bool, str (optional)
            Flag whether to remove gaps in TDI from start and end. If True,
            time length t0 worth of data at the start and end of the waveform
            will be cut from TDI channels. If 'zero', time length t0 worth of
            edge data will be zeroed. If False, TDI channels will not be
            modified. Default True.

        t0 : float (optional)
            Time length in seconds to pad/cut from the start and end of
            the data if pad_data/remove_garbage is True. Default 10000.

        Returns
        -------
        dict
            The TDI observables keyed by their corresponding TDI channel.
        """
        self.pad_data = pad_data

        # get dt from waveform data
        self.dt = hp.delta_t

        # save params for LISA time conversion
        self.beta = beta
        self.lamb = lamb
        self.pol = polarization

        # get index corresponding to time length t0
        if t0 is not None:
            self.t0 = t0
        if pad_data or remove_garbage:
            global pad_idx
            pad_idx = int(self.t0/self.dt)

        # pad the data with zeros
        ### this assumes that the signal naturally tapers to zero
        ### this will not work with e.g. GBs or sinusoids
        if pad_data:
            hp.prepend_zeros(pad_idx)
            hp.append_zeros(pad_idx)
            hc.prepend_zeros(pad_idx)
            hc.append_zeros(pad_idx)

        # set use_gpu
        if use_gpu is None:
            use_gpu = self.use_gpu

        # generate the Doppler time series
        self.get_links(hp, hc, lamb, beta, polarization=polarization,
                       reference_time=reference_time, use_gpu=use_gpu)
        print('get links')

        # set TDI configuration (let FLR handle if not 1 or 2)
        if tdi == 1:
            tdi_opt = '1st generation'
        elif tdi == 2:
            tdi_opt = '2nd generation'
        else:
            tdi_opt = tdi

        if tdi_opt != self.response_init.tdi:
            # update TDI in existing response_init class
            self.response_init.tdi = tdi_opt
            self.response_init._init_TDI_delays()

        # set TDI channels
        if tdi_chan in ['XYZ', 'AET', 'AE']:
            self.response_init.tdi_chan = tdi_chan
        else:
            raise ValueError('TDI channels must be one of: XYZ, AET, AE')

        # if TDI orbit class is provided, update the response_init
        # tdi_orbits are set to class input automatically by FLR otherwise
        if tdi_orbits is not None:
            tdi_orbits.configure(t_arr=self.sample_times)
            self.response_init.tdi_orbits = tdi_orbits

        # generate the TDI channels
        tdi_obs = self.response_init.get_tdi_delays()
        print('tdi complete')

        # processing
        tdi_dict = {}
        self.sample_times -= self.offset
        self.ref_time -= self.offset
        print('start preprocessing')

        for i in range(len(tdi_chan)):
            # save as TimeSeries with LISA frame times
            tdi_dict[tdi_chan[i]] = TimeSeries(tdi_obs[i], delta_t=self.dt,
                                               epoch=self.ref_time_LISA)
            print(f'saved {i} to TimeSeries')

            # treat start and end gaps
            if remove_garbage:
                if remove_garbage == 'zero':
                    # zero the edge data
                    tdi_dict[tdi_chan[i]][:pad_idx] = 0
                    tdi_dict[tdi_chan[i]][-pad_idx:] = 0
                elif type(remove_garbage) == bool:
                    # cut the edge data
                    slc = slice(pad_idx, -pad_idx)
                    tdi_dict[tdi_chan[i]] = tdi_dict[tdi_chan[i]][slc]
                    if i == 0:
                        # update sample times once
                        self.sample_times = tdi_dict[tdi_chan[i]].sample_times
                else:
                    raise ValueError('remove_garbage arg must be a bool ' +
                                     'or "zero"')
            print(f'finished postprocessing {i}')

        return tdi_dict

    @property
    def ref_time_LISA(self):
        """
        Signal start time converted to LISA frame.
        """
        params = [self.ref_time, self.lamb, self.beta, self.pol]
        assert all(i is not None for i in params), ("Need to run project_wave for conversion")

        # convert ref time to LISA
        ssb_start = self.ref_time.gpsSeconds + 1e-9*self.ref_time.gpsNanoSeconds
        lisa_start, _, _, _ = ssb_to_lisa(t_ssb = ssb_start,
                                          longitude_ssb = self.lamb,
                                          latitude_ssb = self.beta,
                                          polarization_ssb = self.pol,
                                          t0=self.offset)

        return lisa_start

    @property
    def sample_times_LISA(self):
        """
        Signal sample times converted to LISA frame.
        """
        diff = self.ref_time_LISA - self.ref_time
        return self.sample_times + diff


def ppdets(ifos, separator=', '):
    """Pretty-print a list (or set) of detectors: return a string listing
    the given detectors alphabetically and separated by the given string
    (comma by default).
    """
    if ifos:
        return separator.join(sorted(ifos))
    return 'no detectors'
