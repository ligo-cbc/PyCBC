# Copyright (C) 2016  Christopher M. Biwer
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
This modules provides functions for calculating the autocorrelation function
and length of a data series.
"""

import numpy
from math import isnan
from pycbc.filter.matchedfilter import correlate
from pycbc.types import FrequencySeries, TimeSeries, zeros

def calculate_acf(data, delta_t=1.0, norm=True):
    """ Calculates the autocorrelation function (ACF) and returns the one-sided
    ACF.

    ACF is estimated using

        \hat{R}(k) = \frac{1}{\left( n-k \right) \sigma^{2}} \sum_{t=1}^{n-k} \left( X_{t} - \mu \right) \left( X_{t+k} - \mu \right) 

    Where \hat{R}(k) is the ACF, X_{t} is the data series at time t, \mu is the
    mean of X_{t}, and \sigma^{2} is the variance of X_{t}.

    Parameters
    -----------
    data : {TimeSeries, numpy.array}
        A TimeSeries or numpy.array of data.
    delta_t : float
        The time step of the data series if it is not a TimeSeries instance.
    norm : bool
        Default is true to normalize by the variance. If False normalize by the
        zero-lag element, ie. the first value of the unnormalized ACF.

    Returns
    -------
    acf : numpy.array
        If data is a TimeSeries then acf will be a TimeSeries of the
        one-sided ACF. Else acf is a numpy.array.
    """

    # if given a TimeSeries instance then get numpy.array
    if isinstance(data, TimeSeries):
        y = data.numpy()
        delta_t = data.delta_t
    else:
        y = data

    # FFT data minus the mean
    fdata = TimeSeries(y-y.mean(), delta_t=delta_t).to_frequencyseries()

    # correlate
    # do not need to give the congjugate since correlate function does it
    cdata = FrequencySeries(zeros(len(fdata), dtype=numpy.complex64),
                           delta_f=fdata.delta_f, copy=False)
    correlate(fdata, fdata, cdata)

    # IFFT correlated data
    acf = cdata.to_timeseries()

    # normalize
    # note that ACF is function of k and we have a factor of n-k
    # at each k so the array here is a vectorized version of computing it
    if norm:
        acf /= ( y.var() * numpy.arange(len(acf), 0, -1) )
    else:
        acf /= acf[0]

    # return input datatype
    if isinstance(data, TimeSeries):
        return TimeSeries(acf, delta_t=delta_t)
    else:
        return acf

def calculate_acl(data, m=5, k=2, dtype=int):
    """ Calculates the autocorrelation length (ACL).

    ACL is estimated using

        r = 1 + 2 \sum_{k=1}^{n} \hat{R}(k)

    Where r is the ACL and \hat{R}(k) is the ACF.

    The parameter k sets the maximum samples to use in calculation of ACL.

    The parameter m controls the length of the window that is summed to
    compute the ACL.

    Parameters
    -----------
    data : {TimeSeries, numpy.array}
        A TimeSeries or numpy.array of data.
    dtype : {int, float}
        The datatype of the output.

    Returns
    -------
    acl : {int, float}
        The ACL. If ACL can not be estimated then returns numpy.inf. If data
        was a TimeSeries then the ACL will be the number of samples times the
        delta_t attribute.
    """

    # calculate ACF that is normalized by the zero-lag value
    acf = calculate_acf(data, norm=False)

    # multiply all values beyond the zero-lag value by 2
    acf[1:] *= 2.0

    # the maximum index to calculate ACF up until
    imax = int(len(acf)/k)

    # sanity check ACF
    if isnan(acf[0]):
        return numpy.inf
    assert acf[0] == 1.0

    # calculate cumlative ACL
    cum_acl = acf[0]
    for i,val in enumerate(acf[1:imax]):
        if cum_acl+val < float(i+1)/m:
            return numpy.ceil(cum_acl)
        cum_acl += val

    return numpy.inf


