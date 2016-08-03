# Copyright (C) 2016  Alex Nitz, Collin Capano
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
""" Utilities for handling frequency compressed an unequally spaced frequency
domain waveforms.
"""
import lalsimulation, lal, numpy, logging, h5py
from pycbc import pnutils, filter
from pycbc.types import Array
from pycbc.opt import omp_libs, omp_flags
from pycbc import WEAVE_FLAGS
from scipy.weave import inline
from scipy import interpolate
from pycbc.types import Array, FrequencySeries, zeros, complex_same_precision_as, real_same_precision_as
from pycbc.waveform import utils

def rough_time_estimate(m1, m2, flow, fudge_length=1.1, fudge_min=0.02):
    """ A very rough estimate of the duration of the waveform.

    An estimate of the waveform duration starting from flow. This is intended
    to be fast but not necessarily accurate. It should be an overestimate of
    the length. It is derived from a simplification of the 0PN post-newtonian
    terms and includes a fudge factor for possible ringdown, etc.

    Parameters
    ----------
    m1: float
        mass of first component object in solar masses
    m2: float
        mass of second component object in solar masses
    flow: float
        starting frequency of the waveform
    fudge_length: optional, {1.1, float}
        Factor to multiply length estimate by to ensure it is a convservative
        value
    fudge_min: optional, {0.2, float}
        Minimum signal duration that can be returned. This should be long
        enough to encompass the ringdown and errors in the precise end time.

    Returns
    -------
    time: float
        Time from flow untill the end of the waveform
    """
    m = m1 + m2
    msun = m * lal.MTSUN_SI
    t =  5.0 / 256.0 * m * m * msun / (m1 * m2) / \
        (numpy.pi * msun * flow) **  (8.0 / 3.0)

    # fudge factoriness
    return .022 if t < 0 else (t + fudge_min) * fudge_length 

def mchirp_compression(m1, m2, fmin, fmax, min_seglen=0.02, df_multiple=None):
    """Return the frequencies needed to compress a waveform with the given
    chirp mass. This is based on the estimate in rough_time_estimate.

    Parameters
    ----------
    m1: float
        mass of first component object in solar masses
    m2: float
        mass of second component object in solar masses
    fmin : float
        The starting frequency of the compressed waveform.
    fmax : float
        The ending frequency of the compressed waveform.
    min_seglen : float
        The inverse of this gives the maximum frequency step that is used.
    df_multiple : {None, float}
        Make the compressed sampling frequencies a multiple of the given value.
        If None provided, the returned sample points can have any floating
        point value.

    Returns
    -------
    array
        The frequencies at which to evaluate the compressed waveform.
    """
    sample_points = []
    f = fmin
    while f < fmax:
        if df_multiple is not None:
            f = int(f/df_multiple)*df_multiple
        sample_points.append(f)
        f += 1.0 / rough_time_estimate(m1, m2, f, fudge_min=min_seglen)
    # add the last point
    if sample_points[-1] < fmax:
        sample_points.append(fmax)
    return numpy.array(sample_points)

def spa_compression(htilde, fmin, fmax, min_seglen=0.02,
        sample_frequencies=None):
    """Returns the frequencies needed to compress the given frequency domain
    waveform. This is done by estimating t(f) of the waveform using the
    stationary phase approximation.

    Parameters
    ----------
    htilde : FrequencySeries
        The waveform to compress.
    fmin : float
        The starting frequency of the compressed waveform.
    fmax : float
        The ending frequency of the compressed waveform.
    min_seglen : float
        The inverse of this gives the maximum frequency step that is used.
    sample_frequencies : {None, array}
        The frequencies that the waveform is evaluated at. If None, will
        retrieve the frequencies from the waveform's sample_frequencies
        attribute.

    Returns
    -------
    array
        The frequencies at which to evaluate the compressed waveform.
    """
    if sample_frequencies is None:
        sample_frequencies = htilde.sample_frequencies.numpy()
    kmin = int(fmin/htilde.delta_f)
    kmax = int(fmax/htilde.delta_f)
    tf = abs(utils.time_from_frequencyseries(htilde,
            sample_frequencies=sample_frequencies).data[kmin:kmax])
    sample_frequencies = sample_frequencies[kmin:kmax]
    sample_points = []
    f = fmin
    while f < fmax:
        f = int(f/htilde.delta_f)*htilde.delta_f
        sample_points.append(f)
        jj = numpy.searchsorted(sample_frequencies, f)
        f += 1./(tf[jj:].max()+min_seglen)
    # add the last point
    if sample_points[-1] < fmax:
        sample_points.append(fmax)
    return numpy.array(sample_points)

compression_algorithms = {
        'mchirp': mchirp_compression,
        'spa': spa_compression
        }

def _vecdiff(htilde, hinterp, fmin, fmax):
    return abs(filter.overlap_cplx(htilde, htilde,
                          low_frequency_cutoff=fmin,
                          high_frequency_cutoff=fmax,
                          normalized=False)
                - filter.overlap_cplx(htilde, hinterp,
                          low_frequency_cutoff=fmin,
                          high_frequency_cutoff=fmax,
                          normalized=False))

def vecdiff(htilde, hinterp, sample_points):
    """Computes a statistic indicating between which sample points a waveform
    and the interpolated waveform differ the most.
    """
    vecdiffs = numpy.zeros(sample_points.size-1, dtype=float)
    for kk,thisf in enumerate(sample_points[:-1]):
        nextf = sample_points[kk+1]
        vecdiffs[kk] = abs(_vecdiff(htilde, hinterp, thisf, nextf))
    return vecdiffs

def compress_waveform(htilde, sample_points, tolerance, interpolation,
        decomp_scratch=None):
    """Retrieves the amplitude and phase at the desired sample points, and adds
    frequency points in order to ensure that the interpolated waveform
    has a mismatch with the full waveform that is <= the desired tolerance. The
    mismatch is computed by finding 1-overlap between `htilde` and the
    decompressed waveform; no maximimization over phase/time is done, nor is
    any PSD used.
    
    .. note::
        The decompressed waveform is only garaunteed to have a true mismatch
        <= the tolerance for the given `interpolation` and for no PSD.
        However, since no maximization over time/phase is performed when
        adding points, the actual mismatch between the decompressed waveform
        and `htilde` is better than the tolerance, using no PSD. Using a PSD
        does increase the mismatch, and can lead to mismatches > than the
        desired tolerance, but typically by only a factor of a few worse.

    Parameters
    ----------
    htilde : FrequencySeries
        The waveform to compress.
    sample_points : array
        The frequencies at which to store the amplitude and phase. More points
        may be added to this, depending on the desired tolerance.
    tolerance : float
        The maximum mismatch to allow between a decompressed waveform and
        `htilde`.
    interpolation : str
        The interpolation to use for decompressing the waveform when computing
        overlaps.
    decomp_scratch : {None, FrequencySeries}
        Optionally provide scratch space for decompressing the waveform. The
        provided frequency series must have the same `delta_f` and length
        as `htilde`.

    Returns
    -------
    CompressedWaveform
        The compressed waveform data; see `CompressedWaveform` for details.
    """
    fmin = sample_points.min()
    df = htilde.delta_f
    sample_index = (sample_points / df).astype(int)
    amp = utils.amplitude_from_frequencyseries(htilde)
    phase = utils.phase_from_frequencyseries(htilde)

    comp_amp = amp.take(sample_index)
    comp_phase = phase.take(sample_index)
    if decomp_scratch is None:
        outdf = df
    else:
        outdf = None
    out = decomp_scratch
    hdecomp = fd_decompress(comp_amp, comp_phase, sample_points,
        out=decomp_scratch, df=outdf, f_lower=fmin,
        interpolation=interpolation)
    mismatch = 1. - filter.overlap(hdecomp, htilde, low_frequency_cutoff=fmin)
    if mismatch > tolerance:
        # we'll need the difference in the waveforms as a function of frequency
        vecdiffs = vecdiff(htilde, hdecomp, sample_points)

    # We will find where in the frequency series the interpolated waveform
    # has the smallest overlap with the full waveform, add a sample point
    # there, and re-interpolate. We repeat this until the overall mismatch
    # is > than the desired tolerance 
    added_points = []
    while mismatch > tolerance:
        minpt = vecdiffs.argmax()
        # add a point at the frequency halfway between minpt and minpt+1
        add_freq = sample_points[[minpt, minpt+1]].mean()
        addidx = int(add_freq/df)
        new_index = numpy.zeros(sample_index.size+1, dtype=int)
        new_index[:minpt+1] = sample_index[:minpt+1]
        new_index[minpt+1] = addidx
        new_index[minpt+2:] = sample_index[minpt+1:]
        sample_index = new_index
        sample_points = (sample_index * df).astype(
            real_same_precision_as(htilde))
        # get the new compressed points
        comp_amp = amp.take(sample_index)
        comp_phase = phase.take(sample_index)
        # update the vecdiffs and mismatch
        hdecomp = fd_decompress(comp_amp, comp_phase, sample_points,
            out=decomp_scratch, df=outdf, f_lower=fmin,
            interpolation=interpolation)
        new_vecdiffs = numpy.zeros(vecdiffs.size+1)
        new_vecdiffs[:minpt] = vecdiffs[:minpt]
        new_vecdiffs[minpt+2:] = vecdiffs[minpt+1:]
        new_vecdiffs[minpt:minpt+2] = vecdiff(htilde, hdecomp,
            sample_points[minpt:minpt+2])
        vecdiffs = new_vecdiffs
        mismatch = 1. - filter.overlap(hdecomp, htilde,
            low_frequency_cutoff=fmin)
        added_points.append(addidx)
    logging.info("mismatch: %f, N points: %i (%i added)" %(mismatch,
        len(comp_amp), len(added_points)))
    
    return CompressedWaveform(sample_points, comp_amp, comp_phase,
                interpolation=interpolation, tolerance=tolerance,
                mismatch=mismatch)


_linear_decompress_code = r"""
    #include <math.h>
    # include <stdio.h>
    // cast the output to a float array for faster processing
    // this takes advantage of the fact that complex arrays store
    // their real and imaginary values next to each other in memory
    double* outptr = (double*) h;

    // zero out the beginning
    memset(outptr, 0, sizeof(*outptr)*2*imin);

    outptr += 2*imin; // move to the start position

    // variables for computing the interpolation
    double df = (double) delta_f;
    double sf = 0.;
    double A = 0.;
    double nextA = 0.;
    double phi = 0.;
    double nextPhi = 0.;
    double next_sf = sample_frequencies[jmin];
    double f = 0.;
    double invsdf = 0.;
    double mAmp = 0.;
    double bAmp = 0.;
    double mPhi = 0.;
    double bPhi = 0.;
    double interpAmp = 0.;
    double interpPhi = 0.;

    // variables for updating each interpolated frequency
    double h_re = 0.;
    double h_im = 0.;
    double incrh_re = 0.;
    double incrh_im = 0.;
    double g_re = 0.;
    double g_im = 0.;
    double incrg_re = 0.;
    double incrg_im = 0.;
    double dPhi_re = 0.;
    double dPhi_im = 0.;

    // jj keeps track of where in the sample_frequencies we are
    int jj = jmin-1;

    // we will re-compute cos/sin of the phase at the following intervals:
    int update_interval = 100;

    // kk keeps track of how many steps into the update interval we are
    int kk = update_interval;
    
    // cycle over desired samples
    for (int ii=imin; ii<flen; ii++){
        f = ii*df;
        if (f >= next_sf){
            // update linear interpolations
            jj += 1;
            // if we have gone beyond the sampled frequencies, just break
            if ((jj+1) == sflen) {
                // zero out the rest of the array
                memset(outptr, 0, 2*(flen-ii));
                break;
            }
            sf = (double) sample_frequencies[jj];
            next_sf = (double) sample_frequencies[jj+1];
            A = (double) amp[jj];
            nextA = (double) amp[jj+1];
            phi = (double) phase[jj];
            nextPhi = (double) phase[jj+1];
            invsdf = 1./(next_sf - sf);
            mAmp = (nextA - A)*invsdf;
            bAmp = A - mAmp*sf;
            mPhi = (nextPhi - phi)*invsdf;
            bPhi = phi - mPhi*sf;
            // set the step counter to the update interval to force a
            // reevaluation
            kk = update_interval;
        }
        if (kk == update_interval){
            // update the amp and phase and h with their exact values
            interpAmp = mAmp * f + bAmp;
            interpPhi = mPhi * f + bPhi;
            dPhi_re = cos(mPhi * df);
            dPhi_im = sin(mPhi * df);
            h_re = interpAmp * cos(interpPhi);
            h_im = interpAmp * sin(interpPhi);
            g_re = mAmp * df * cos(interpPhi);
            g_im = mAmp * df * sin(interpPhi);
            kk = 0;
        }
        else {
            // compute h by incrementing the last h
            incrh_re = h_re * dPhi_re - h_im * dPhi_im;
            incrh_im = h_re * dPhi_im + h_im * dPhi_re;
            incrg_re = g_re * dPhi_re - g_im * dPhi_im;
            incrg_im = g_re * dPhi_im + g_im * dPhi_re;
            h_re = incrh_re + incrg_re;
            h_im = incrh_im + incrg_im;
            g_re = incrg_re;
            g_im = incrg_im;
            kk += 1;
        }
        *outptr = h_re;
        *(outptr+1) = h_im;
        outptr += 2;
    }
"""
# for single precision
_linear_decompress_code32 = _linear_decompress_code.replace('double', 'float')

_precision_map = {
    'float32': 'single',
    'float64': 'double',
    'complex64': 'single',
    'complex128': 'double'
}

_complex_dtypes = {
    'single': numpy.complex64,
    'double': numpy.complex128
}

_real_dtypes = {
    'single': numpy.float32,
    'double': numpy.float64
}

def fd_decompress(amp, phase, sample_frequencies, out=None, df=None,
        f_lower=None, interpolation='linear'):
    """Decompresses an FD waveform using the given amplitude, phase, and the
    frequencies at which they are sampled at.

    Parameters
    ----------
    amp : array
        The amplitude of the waveform at the sample frequencies.
    phase : array
        The phase of the waveform at the sample frequencies.
    sample_frequencies : array
        The frequency (in Hz) of the waveform at the sample frequencies.
    out : {None, FrequencySeries}
        The output array to save the decompressed waveform to. If this contains
        slots for frequencies > the maximum frequency in sample_frequencies,
        the rest of the values are zeroed. If not provided, must provide a df.
    df : {None, float}
        The frequency step to use for the decompressed waveform. Must be
        provided if out is None.
    f_lower : {None, float}
        The frequency to start the decompression at. If None, will use whatever
        the lowest frequency is in sample_frequencies. All values at
        frequencies less than this will be 0 in the decompressed waveform.
    interpolation : {'linear', str}
        The interpolation to use for the amplitude and phase. Default is
        'linear'. If 'linear' a custom interpolater is used. Otherwise,
        ``scipy.interpolate.interp1d`` is used; for other options, see
        possible values for that function's ``kind`` argument.

    Returns
    -------
    out : FrqeuencySeries
        If out was provided, writes to that array. Otherwise, a new
        FrequencySeries with the decompressed waveform.
    """
    precision = _precision_map[sample_frequencies.dtype.name]
    if _precision_map[amp.dtype.name] != precision or \
            _precision_map[phase.dtype.name] != precision:
        raise ValueError("amp, phase, and sample_points must all have the "
            "same precision")
    if out is None:
        if df is None:
            raise ValueError("Either provide output memory or a df")
        flen = int(numpy.ceil(sample_frequencies.max()/df+1))
        out = FrequencySeries(numpy.zeros(flen,
            dtype=_complex_dtypes[precision]), copy=False,
            delta_f=df)
    else:
        # check for precision compatibility
        if out.precision == 'double' and precision == 'single':
            raise ValueError("cannot cast single precision to double")
        df = out.delta_f
        flen = len(out)
    if f_lower is None:
        jmin = 0
        f_lower = sample_frequencies[0]
    else:
        if f_lower >= sample_frequencies.max():
            raise ValueError("f_lower is > than the maximum sample frequency")
        jmin = int(numpy.searchsorted(sample_frequencies, f_lower))
    imin = int(numpy.floor(f_lower/df))
    # interpolate the amplitude and the phase
    if interpolation == "linear":
        if precision == 'single':
            code = _linear_decompress_code32
        else:
            code = _linear_decompress_code
        # use custom interpolation
        sflen = len(sample_frequencies)
        h = numpy.array(out.data, copy=False)
        delta_f = float(df)
        inline(code, ['flen', 'sflen', 'delta_f', 'sample_frequencies',
                      'amp', 'phase', 'h', 'imin', 'jmin'],
               extra_compile_args=[WEAVE_FLAGS + '-march=native -O3 -w'] +\
                                  omp_flags,
               libraries=omp_libs)
    else:
        # use scipy for fancier interpolation
        outfreq = out.sample_frequencies.numpy()
        amp_interp = interpolate.interp1d(sample_frequencies.numpy(),
            amp.numpy(), kind=interpolation, bounds_error=False, fill_value=0.,
            assume_sorted=True)
        phase_interp = interpolate.interp1d(sample_frequencies.numpy(),
            phase.numpy(), kind=interpolation, bounds_error=False,
            fill_value=0., assume_sorted=True)
        A = amp_interp(outfreq)
        phi = phase_interp(outfreq)
        out.data[:] = A*numpy.cos(phi) + (1j)*A*numpy.sin(phi)
    return out


class CompressedWaveform(object):
    """Class that stores information about a compressed waveform.
    
    Parameters
    ----------
    sample_points : {array, h5py.Dataset}
        The frequency points at which the compressed waveform is sampled.
    amplitude : {array, h5py.Dataset}
        The amplitude of the waveform at the given `sample_points`.
    phase : {array, h5py.Dataset}
        The phase of the waveform at the given `sample_points`.
    interpolation : {None, str}
        The interpolation that was used when compressing the waveform for
        computing tolerance. This is also the default interpolation used when
        decompressing; see `decompress` for details.
    tolerance : {None, float}
        The tolerance that was used when compressing the waveform.
    mismatch : {None, float}
        The actual mismatch between the decompressed waveform (using the given
        `interpolation`) and the full waveform.
    load_to_memory : {True, bool}
        If `sample_points`, `amplitude`, and/or `phase` is an hdf dataset, they
        will be cached in memory the first time they are accessed. Default is
        True.

    Attributes
    ----------
    sample_points : array
        The frequencies at which the compressed waveform is sampled. This is
        always returned as an array, even if the stored `sample_points` is an
        hdf dataset. If `load_to_memory` is True and the stored points are
        an hdf dataset, the `sample_points` will cached in memory the first
        time this attribute is accessed.
    amplitude : array
        The amplitude of the waveform at the `sample_points`. This is always
        returned as an array; the same logic as for `sample_points` is used
        to determine whether or not to cache in memory.
    phase : array
        The phase of the waveform as the `sample_points`. This is always
        returned as an array; the same logic as for `sample_points` is used to
        determine whether or not to cache in memory.
    load_to_memory : bool
        Whether or not to load `sample_points`/`amplitude`/`phase` into memory
        the first time they are accessed, if they are hdf datasets. Can be
        set directly to toggle this behavior.
    interpolation : str
        The interpolation that was used when compressing the waveform, for
        checking the mismatch. Also the default interpolation used when
        decompressing.
    tolerance : {None, float}
        The tolerance that was used when compressing the waveform.
    mismatch : {None, float}
        The mismatch between the decompressed waveform and the original
        waveform.

    Methods
    -------
    decompress :
        Decompresses the waveform to the desired sampling.
    write_to_hdf :
        Writes the compressed waveform to an open hdf file.
    clear_cache :
        Clears the in-memory cache used to hold the
        `sample_points`/`amplitude`/`phase`; only relevant if `load_to_memory`
        is True.

    Class Methods
    -------------
    from_hdf :
        Loads a compressed waveform from the given open hdf file.
    """
    
    def __init__(self, sample_points, amplitude, phase,
            interpolation=None, tolerance=None, mismatch=None,
            load_to_memory=True):
        self._sample_points = sample_points
        self._amplitude = amplitude
        self._phase = phase
        self._cache = {}
        self.load_to_memory = load_to_memory
        # metadata
        self.interpolation = interpolation
        self.tolerance = tolerance
        self.mismatch = mismatch

    def _get(self, param):
        val = getattr(self, '_%s' %param)
        if isinstance(val, h5py.Dataset):
            try:
                val = self._cache[param]
            except KeyError:
                val = val[:]
                if self.load_to_memory:
                    self._cache[param] = val
        return val

    @property
    def amplitude(self):
        return self._get('amplitude')

    @property
    def phase(self):
        return self._get('phase')

    @property
    def sample_points(self):
        return self._get('sample_points')

    def clear_cache(self):
        """Clear self's cache of amplitude, phase, and sample_points."""
        self._cache.clear()

    def decompress(self, out=None, df=None, f_lower=None, interpolation=None):
        """Decompress self.
        
        Parameters
        ----------
        out : {None, FrequencySeries}
            Write the decompressed waveform to the given frequency series. The
            decompressed waveform will have the same `delta_f` as `out`.
            Either this or `df` must be provided.
        df : {None, float}
            Decompress the waveform such that its `delta_f` has the given
            value. Either this or `out` must be provided.
        f_lower : {None, float}
            The starting frequency at which to decompress the waveform. Cannot
            be less than the minimum frequency in `sample_points`. If `None`
            provided, will default to the minimum frequency in `sample_points`.
        interpolation : {None, str}
            The interpolation to use for decompressing the waveform. If `None`
            provided, will default to `self.interpolation`.

        Returns
        -------
        FrequencySeries
            The decompressed waveform.
        """
        if f_lower is None:
            # use the minimum of the samlpe points
            f_lower = self.sample_points.min()
        if interpolation is None:
            interpolation = self.interpolation
        return fd_decompress(self.amplitude, self.phase, self.sample_points,
            out=out, df=df, f_lower=f_lower, interpolation=interpolation)

    def write_to_hdf(self, fp, template_hash, root=None):
        """Write the compressed waveform to the given hdf file handler.

        The waveform is written to:
        `fp['[{root}/]compressed_waveforms/{template_hash}/{param}']`,
        where `param` is the `sample_points`, `amplitude`, and `phase`. The
        `interpolation`, `tolerance`, and `mismatch` are saved to the group's
        attributes.

        Parameters
        ----------
        fp : h5py.File
            An open hdf file to write the compressed waveform to.
        template_hash : {hash, int, str}
            A hash, int, or string to map the template to the waveform.
        root : {None, str}
            Put the `compressed_waveforms` group in the given directory in the
            hdf file. If `None`, `compressed_waveforms` will be the root
            directory.
        """
        if root is None:
            root = ''
        else:
            root = '%s/'%(root)
        group = '%scompressed_waveforms/%s' %(root, str(template_hash))
        for param in ['amplitude', 'phase', 'sample_points']:
            fp['%s/%s' %(group, param)] = self._get(param)
        fp[group].attrs['mismatch'] = self.mismatch
        fp[group].attrs['interpolation'] = self.interpolation
        fp[group].attrs['tolerance'] = self.tolerance

    @classmethod
    def from_hdf(cls, fp, template_hash, root=None, load_to_memory=True,
            load_now=False):
        """Load a compressed waveform from the given hdf file handler.

        The waveform is retrieved from:
        `fp['[{root}/]compressed_waveforms/{template_hash}/{param}']`,
        where `param` is the `sample_points`, `amplitude`, and `phase`.

        Parameters
        ----------
        fp : h5py.File
            An open hdf file to write the compressed waveform to.
        template_hash : {hash, int, str}
            The id of the waveform.
        root : {None, str}
            Retrieve the `compressed_waveforms` group from the given string.
            If `None`, `compressed_waveforms` will be assumed to be in the
            top level.
        load_to_memory : {True, bool}
            Set the `load_to_memory` attribute to the given value in the
            returned instance.
        load_now : {False, bool}
            Immediately load the `sample_points`/`amplitude`/`phase` to memory.


        Returns
        -------
        CompressedWaveform
            An instance of this class with parameters loaded from the hdf file.
        """
        if root is None:
            root = ''
        else:
            root = '%s/'%(root)
        group = '%scompressed_waveforms/%s' %(root, str(template_hash))
        sample_points = fp[group]['sample_points']
        amp = fp[group]['amplitude']
        phase = fp[group]['phase']
        if load_now:
            sample_points = sample_points[:]
            amp = amp[:]
            phase = phase[:]
        return cls(sample_points, amp, phase,
            interpolation=fp[group].attrs['interpolation'],
            tolerance=fp[group].attrs['tolerance'],
            mismatch=fp[group].attrs['mismatch'],
            load_to_memory=load_to_memory)

