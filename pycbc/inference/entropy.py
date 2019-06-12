""" The module contains functions for calculating the
Kullback-Leibler divergence.
"""

import numpy

from scipy import stats


def entropy(pdf1, base=numpy.e):
    """ Computes the information entropy for a single parameter
    from one probability density function.

    Parameters
    ----------
    pdf1 : numpy.array
        Probability density function.
    pdf2 : {None, numpy.array}, optional
        Probability density function of a second distribution to
        calculate the Kullback-Leibler divergence.
    base : {numpy.e, numpy.float64}, optional
        The logarithmic base to use (choose base 2 for information measured
        in bits, default is nats).

    Returns
    -------
    numpy.float64
        The information entropy value (or the Kullback-Leibler divergence if
        two distributions are given).
    """

    return stats.entropy(pdf1, base=base)


def kl(samples1, samples2, pdf1=False, pdf2=False, kde=False,
       bins=30, hist_min=None, hist_max=None, base=numpy.e):
    """ Computes the Kullback-Leibler divergence for a single parameter
    from two distributions.

    Parameters
    ----------
    samples1 : numpy.array
        Samples or probability density function (for the latter must also set
        `pdf1=True`).
    samples2 : numpy.array
        Samples or probability density function (for the latter must also set
        `pdf2=True`).
    pdf1 : bool
        Set to `True` if `samples1` is a probability density funtion already.
    pdf2 : bool
        Set to `True` if `samples2` is a probability density funtion already.
    kde : bool
        Set to `True` if at least one of `pdf1` or `pdf2` is `False` to
        estimate the probability density function using kernel density
        estimation (KDE).
    bins : {30, int}, optional
        Number of bins to use when calculating probability density function
        from a set of samples of the distribution. This will be ignored if
        `kde=True`.
    hist_min : numpy.float64
        Minimum of the distributions' values to use. This will be ignored if
        `kde=True`.
    hist_max : numpy.float64
        Maximum of the distributions' values to use. This will be ignored if
        `kde=True`.
    base : numpy.float64
        The logarithmic base to use (choose base 2 for information measured
        in bits, default is nats).

    Returns
    -------
    numpy.float64
        The Kullback-Leibler divergence value.
    """
    if pdf1 and pdf2 and kde:
        raise ValueError('KDE can only be used when at least one of pdf1 or '
                         'pdf2 is False.')

    pdfs = {}
    for n, (samples, pdf) in enumerate(((samples1, pdf1), (samples2, pdf2))):
        if pdf:
            pdfs[n] = samples
        elif kde:
            samples_kde = stats.gaussian_kde(samples)
            pdfs[n] = samples_kde.evaluate(samples)
        else:
            pdfs[n], _ = numpy.histogram(samples, bins=bins,
                                         range=(hist_min, hist_max),
                                         normed=True)
            
    return stats.entropy(pdfs[0], qk=pdfs[1], base=base)


def js(samples1, samples2, kde=False, bins=30, hist_min=None, hist_max=None,
       base=numpy.e):
    """ Computes the Jensen-Shannon divergence for a single parameter
    from two distributions.

    Parameters
    ----------
    samples1 : numpy.array
        Samples.
    samples2 : numpy.array
        Samples.
    kde : bool
        Set to `True` to estimate the probability density function using
        kernel density estimation (KDE).
    bins : {30, int}, optional
        Number of bins to use to calculate the probability density function
        from a set of samples of the distribution. This will be ignored if
        `kde=True`.
    hist_min : numpy.float64
        Minimum of the distributions' values to use. This will be ignored if
        `kde=True`.
    hist_max : numpy.float64
        Maximum of the distributions' values to use. This will be ignored if
        `kde=True`.
    base : numpy.float64
        The logarithmic base to use (choose base 2 for information measured
        in bits, default is nats).

    Returns
    -------
    numpy.float64
        The Jensen-Shannon divergence value.
    """
    join_samples = numpy.concatenate((samples1, samples2))
    if kde:
        samplesm_kde = stats.gaussian_kde(join_samples)
        samplesm = samplesm_kde.evaluate(samplesm)
    else:
        samplesm, _ = numpy.histogram(join_samples, bins=bins,
                                      range=(hist_min, hist_max), normed=True)
    samplesm = (1./2) * samplesm

    js_div = 0
    for samples in (samples1, samples2):
        js_div += (1./2) * kl(samples, samplesm, pdf1=False, pdf2=True,
                              kde=kde, bins=bins, hist_min=hist_min,
                              hist_max=hist_max, base=base)

    return js_div
