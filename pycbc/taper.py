# Copyright (C) 2017  Collin Capano
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
This modules provides classes and functions for tapering data.
"""

import numpy
from scipy import signal
import lalsimulation as sim
from pycbc.types import Array, TimeSeries, FrequencySeries, float32, float64

# values for informing data whitening level
UNWHITENED = 0
WHITENED = 1
OVERWHITENED = 2

#
#   LALSimulation taper
#

# map between tapering string in sim_inspiral table or inspiral 
# code option and lalsimulation constants
laltaper_map = {
    'TAPER_NONE'    : None,
    'TAPER_START'   : sim.SIM_INSPIRAL_TAPER_START,
    'start'         : sim.SIM_INSPIRAL_TAPER_START,
    'TAPER_END'     : sim.SIM_INSPIRAL_TAPER_END,
    'end'           : sim.SIM_INSPIRAL_TAPER_END,
    'TAPER_STARTEND': sim.SIM_INSPIRAL_TAPER_STARTEND,
    'startend'      : sim.SIM_INSPIRAL_TAPER_STARTEND
}

laltaper_func_map = {
    numpy.dtype(float32): sim.SimInspiralREAL4WaveTaper,
    numpy.dtype(float64): sim.SimInspiralREAL8WaveTaper
}

def laltaper_timeseries(tsdata, tapermethod=None, return_lal=False):
    """
    Taper either or both ends of a time series using wrapped 
    LALSimulation functions

    Parameters
    ----------
    tsdata : TimeSeries
        Series to be tapered, dtype must be either float32 or float64
    tapermethod : string
        Should be one of ('TAPER_NONE', 'TAPER_START', 'TAPER_END',
        'TAPER_STARTEND', 'start', 'end', 'startend') - NB 'TAPER_NONE' will
        not change the series!
    return_lal : Boolean
        If True, return a wrapped LAL time series object, else return a 
        PyCBC time series.
    """
    if tapermethod is None:
        raise ValueError("Must specify a tapering method (function was called"
                         "with tapermethod=None)")
    if tapermethod not in laltaper_map.keys():
        raise ValueError("Unknown tapering method %s, valid methods are %s" % \
                         (tapermethod, ", ".join(laltaper_map.keys())))
    if not tsdata.dtype in (float32, float64):
        raise TypeError("Strain dtype must be float32 or float64, not "
                    + str(tsdata.dtype))
    taper_func = laltaper_func_map[tsdata.dtype]
    # make a LAL TimeSeries to pass to the LALSim function
    ts_lal = tsdata.astype(tsdata.dtype).lal()
    if laltaper_map[tapermethod] is not None:
        taper_func(ts_lal.data, laltaper_map[tapermethod])
    if return_lal == True:
        return ts_lal
    else:
        return TimeSeries(ts_lal.data.data[:], delta_t=ts_lal.deltaT,
                          epoch=ts_lal.epoch)


#
#   General taper class
#
class TimeDomainTaper(object):
    """Provides generic taper windows for tapering data in the time domain.

    A left and right taper function may be specified to use different tapers,
    along with a taper duration for each. Tapers are applied such that the
    left taper ramps up to 1 and the right taper ramps down from 1, with zeros
    before/after.

    Instances of this class may be called as a function; the `apply_taper`
    method is called in that case.

    Parameters
    ----------
    left_taper : str or tuple, optional
        The name of the window to use for the left taper. May be either `lal`,
        or any name recognized by `scipy.signal.get_window`. Some taper
        taper functions require an additional parameter to be specified; if so,
        provide a tuple with the first argument the window name and the
        second the parameter. For details, see `scipy.signal.get_window`.
        Default is None, in which case no taper will be applied on the left.
    right_taper : str or tuple, optional
        Same as `left_taper`, but for the right side.
    left_taper_duration : float, optional
        The duration of the taper on the left side. Required for scipy windows.
        A `ValueError` will be raised if `left_taper` is set to 'lal' and this
        is not None. Default is None.
    right_taper_duration : float, optional
        Same as `left_taper_duration`, but for the right side.
    taper_whitened : {False/0, 1, 2}
        Optionally (over-)whiten the data before applying the tapers. If 1,
        data will be whitened; if 2, data will be over-whitened; if 0 or False,
        no whitening will be done. Default is False. If 1 or 2, psds must not
        be None.
    psds : (dict of) FrequencySeries, optional
        Needed if taper_whitened is 1 or 2. Either a FrequencySeries or a
        dictionary of FrequencySeries to use for whitening the data. If a
        dictionary, must be `detector name -> psd`. Default is None.

    See Also
    --------
    scipy.signal.get_window : function for generating windows
    """
    def __init__(self, left_taper=None, right_taper=None,
                 left_taper_duration=None, right_taper_duration=None,
                 taper_whitened=False, psds=None):
        if int(taper_whitened) not in [UNWHITENED, WHITENED, OVERWHITENED]:
            raise ValueError("taper_whitened must be either {} (taper "
                             "before whitening), {} (taper after whitening) "
                             "or {} (taper after overwhitening)".format(
                                UNWHITENED, WHITENED, OVERWHITENED))
        if left_taper == 'lal':
            if left_taper_duration is not None:
                raise ValueError("The lal taper function does not take a "
                                 "duration")
        elif left_taper is not None and left_taper_duration is None:
            raise ValueError("Non-lal taper functions require a duration")
        self.left_taper = left_taper
        self.left_taper_duration = left_taper_duration
        if right_taper == 'lal':
            if right_taper_duration is not None:
                raise ValueError("The lal taper function does not take a "
                                 "duration")
        elif right_taper is not None and right_taper_duration is None:
            raise ValueError("Non-lal taper functions require a duration")
        self.right_taper = right_taper
        self.right_taper_duration = right_taper_duration
        self.taper_whitened = taper_whitened
        self.left_window = {}
        self.right_window = {}
        self.set_psds(psds)
        if self.taper_whitened:
            if psds is None:
                raise ValueError("must provide a psd if tapering "
                                "(over-)whitened waveform")
            if left_taper == 'lal' and right_taper == 'lal':
                raise ValueError("both left and right use lal tapering, but "
                                 "lal tapering cannot be done on whitened "
                                 "waveforms")

    def set_psds(self, psds):
        """Sets the psds attribute and calculates the inverse."""
        self._psds = psds
        self._invasds = None
        if psds is not None:
            # temporarily suppress numpy divide by 0 warning
            numpysettings = numpy.seterr(divide='ignore')
            if not isinstance(psds, dict):
                psds = {None: psds}
            for ifo,psd in psds.items():
                invpsd = 1./psd
                mask = numpy.isinf(_invpsd)
                invpsd[mask] = 0.
                self._invpsds[ifo] = invpsd
            numpy.seterr(**numpysettings)
        else:
            self._invpsds = None

    @property
    def psds(self):
        """Returns the psds attribute."""
        return self._psds

    def whiten_waveform(htilde, ifo=None, copy=False):
        """Whitens the given frequency domain data.

        If `taper_whitened` = 1, the data will be divided by the ASD. If 2,
        the PSD. Otherwise, a ValueError is raised.

        Parameters
        ----------
        htilde : FrequencySeries
            The data in the frequency domain.
        ifo : str, optional
            If `psds` is a dictionary, the psd of the ifo to get.
        copy : bool, optional
            If True, the data will be copied before whitening. Otherwise, the
            data are whitened in place. Default is False.

        Returns
        -------
        FrequencySeries :
            The whitened data.
        """
        if copy:
            htilde = 1.*htilde
        if self.taper_whitened == WHITENED:
            if self._invasds is None:
                self._invasds = {}
            try:
                wh = self._invasds[ifo]
            except KeyError:
                # compute the inverse asd
                wh = self._invpsds[ifo]**0.5
                self._invasds[ifo] = wh
        elif self.taper_whitened == OVERWHITENED:
            wh = self._invpsds[ifo]
        else:
            raise ValueError("taper_whitened set to {}".format(taper_whitened))
        kmax = len(htilde)
        # we can't whiten the waveform if it has frequencies outside of what
        # the psd has
        if kmax > len(wh):
            raise ValueError("htilde goes to higher frequency than the psd")
        htilde *= wh[:kmax]
        return htilde

    def get_left_window(self, delta_t):
        """Returns the left window to use for tapering.

        If the given `delta_t` has not previously been used, the window will
        be generated and cached to the `left_window` dict.

        Parameters
        ----------
        delta_t : float
            The dt of the time series the taper will be applied to.

        Returns
        -------
        Array :
            The window.
        """
        taper_size = int(self.left_taper_duration / delta_t)
        try:
            return self.left_window[taper_size]
        except KeyError:
            # generate the window at this dt
            win = signal.get_window(self.left_taper, 2*taper_size)
            self.left_window[taper_size] = Array(win[:taper_size])
            return self.left_window[taper_size]

    def get_right_window(self, delta_t):
        """Returns the right window to use for tapering.

        If the given `delta_t` has not previously been used, the window will
        be generated and cached to the `right_window` dict.

        Parameters
        ----------
        delta_t : float
            The dt of the time series the taper will be applied to.

        Returns
        -------
        Array :
            The window.
        """
        taper_size = int(self.right_taper_duration / delta_t)
        try:
            return self.right_window[taper_size]
        except KeyError:
            # generate the window at this dt
            win = signal.get_window(self.right_taper, 2*taper_size)
            self.right_window[taper_size] = Array(win[taper_size:])
            return self.right_window[taper_size]


    def apply_taper(self, h, left_time=None, right_time=None, ifo=None,
                    copy=True):
        """Applies the tapers at the given times.

        If `taper_whitened` is 1 or 2, the data will be whitened accordingly
        before applying the tapers.

        If `left_taper` and `right_taper` are both None, this just returns
        (a copy of) the data.

        Parameters
        ----------
        h : TimeSeries or FrequencySeries
            The data to to apply the tapers to.
        left_time : float
            The time at which to start the left taper. If the time is before
            the start time / epoch of the data, only the amount of the taper
            that overlaps the data will be applied. If the entire taper occurs
            before the start of the data, no left taper will be applied.
            This must be provided if `left_taper` is not None or 'lal';
            otherwise, this must be None (the default).
        right_time : float
            The time at which to end the right taper. If the time is after
            the end time of the data (if h is a `FrequencySeries`, this means
            `h.epoch + 1/h.delta_f`), only the amount of the taper that
            overlaps the data will be applied. If the entire taper occurs
            after the end of th data, no right taper will be applied.
            This must be provided if `right_taper` is not None or 'lal';
            otherwise, this must be None (the default).
        ifo : None, optional
            Must be provided if `taper_whitened` is 1 or 2 and `psds` is a
            dictionary of psds.
        copy : bool, optional
            Whether to copy the data before applying the taper/whitening. If
            False, the taper will be applied in place. Default is False.

        Returns
        -------
        TimeSeries or FrequencySeries
            The tapered data. If a FrequencySeries was provided, a
            FrequencySeries will be returned. Otherwise, a TimeSeries. If
            `taper_whitened` is 1 or 2, the returned data will be
            (over-)whitened.
        """
        if copy:
            h = 1*h
        if isinstance(h, FrequencySeries):
            ht = None
            hf = h
            return_f = True
        else:
            ht = h
            hf = None
            return_f = False
        # lal taper function needs to be applied before whitening
        if self.left_taper == 'lal' or \
                self.right_taper == 'lal':
            if ht is None:
                ht = hf.to_timeseries()
            tmeth = ''
            if self.left_taper == 'lal':
                tmeth = 'start'
            if self.right_taper == 'lal':
                tmeth = ''.join([tmeth, 'end'])
            ht = laltaper_timeseries(ht, tapermethod=tmeth)
            hf = None
            if tmeth == 'startend':
                # just return, since there's nothing else to do
                if return_f:
                    return ht.to_frequencyseries()
                else:
                    return ht
        # check that a time is provided
        if self.left_taper is not None and left_time is None:
            raise ValueError("must provide a time for non-lal tapers")
        if self.right_taper is not None and right_time is None:
            raise ValueError("must provide a time for non-lal tapers")
        #
        #   Whiten
        #
        if self.taper_whitened:
            if hf is None:
                hf = ht.to_frequencyseries(delta_f=self.psds[ifo].delta_f)
            self.whiten_waveform(hf, ifo=ifo, copy=False)
            ht = hf.to_timeseries()
        elif ht is None:
            ht = hf.to_timeseries()
        # 
        #   apply left taper
        #
        if left_time is not None:
            if right_time is not None and right_time <= left_time:
                raise ValueError("right_time must be > left_time")
            win = self.get_left_window(ht.delta_t)
            left_time = left_time - float(ht.start_time)
            startidx = max(int(left_time / ht.delta_t), 0)
            if startidx < len(ht):
                endidx = max(min(startidx + len(win), len(ht)), 0)
                if startidx != endidx:
                    ht[startidx:endidx] *= win[-(endidx-startidx):]
                    if startidx != 0:
                        ht[:startidx] = 0.
        #
        #   apply right taper
        #
        if right_time is not None:
            win = self.get_right_window(ht.delta_t)
            right_time = right_time - float(ht.start_time)
            endidx = min(int(numpy.ceil(right_time / ht.delta_t)), len(ht))
            if endidx > 0:
                startidx = min(max(endidx - len(win), 0), len(ht))
                if startidx != endidx:
                    ht[startidx:endidx] *= win[:endidx-startidx]
                    if endidx != len(ht):
                        ht[endidx:] = 0.
        #
        #   Return
        #
        if return_f:
            return ht.to_frequencyseries()
        else:
            return ht

    __call__ = apply_taper

    @classmethod
    def from_config(cls, cp, section='taper', psds=None):
        """Initializes and instance of this class from the given config file.

        If a window requires additional parameters to be specified, they
        should be specifed as `(left|right)-taper-param`. All other arguments
        in the given section will be passed to the class as keyword arguments,
        with dashes replaced with underscores. For example, the following will
        return a taper instance that applies a kaiser window on the left with
        `beta=8`, and no window on the right:

        .. code-block:: ini

            [{section}]
            left-taper = kaiser
            left-taper-param = 8
            left-taper-duration = 4

        Parameters
        ----------
        cp : ConfigParser
            Config file parser to retrieve the settings from.
        section : str, optional
            The section to retrieve the results from. Default is 'taper'.
        psds : (dict of) FrequencySeries, optional
            The psd(s) to use for whitening. Must be provided if
            `taper-whitened` is in the config file and is set to 1 or 2.
        
        Returns
        -------
        TimeDomainTaper :
            Instance of this class initialized with the parameters specified
            in the config file.
        """
        opts = {}
        # parse the whitening
        if cp.has_option(section, 'taper-whitened'):
            taper_whitened = cp.get(section, 'taper-whitened')
            try:
                taper_whitened = int(taper_whitened)
            except ValueError:
                raise ValueError("taper-whitened must be either 0 (no "
                                 "whitening), 1 (whiten), or 2 (overwhiten)")
            opts['taper_whitened'] = taper_whitened
            opts['psds'] = psds
        # get everything else
        for opt in cp.options(section):
            if opt == 'taper-whitened':
                continue
            val = cp.get(section, opt)
            try:
                val = float(val)
            except ValueError:
                pass
            opts[opt.replace('-', '_')] = val
        # if taper parameters were provided, add to the appropriate taper opt
        taper_param = opts.pop('left_taper_param', None)
        if taper_param is not None:
            try:
                opts['left_taper'] = (opts['left_taper'], taper_param)
            except KeyError:
                raise ValueError("left_taper_param provided, but no "
                                 "left_taper")
        taper_param = opts.pop('right_taper_param', None)
        if taper_param is not None:
            try:
                opts['right_taper'] = (opts['right_taper'], taper_param)
            except KeyError:
                raise ValueError("right_taper_param provided, but no "
                                 "right_taper")
        return cls(**opts)


__all__ = ['TimeDomainTaper']
