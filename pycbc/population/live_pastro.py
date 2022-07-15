import json
import h5py
import numpy
import logging
from lal import YRJUL_SI as lal_s_per_yr
from pycbc.tmpltbank import bank_conversions as bankconv
from pycbc.events import triggers
from . import fgmc_functions as fgmcfun


def read_template_param_bin_data(spec_file):
    """
    Parameters
    ----------
    spec_file: string
        Name of json file containing various static data

    Returns
    -------
    pa_spec: dictionary
        Prerequisite data for p astro calc
    """
    with open(spec_file) as specf:
        pa_spec = json.load(specf)
    # check that the file has the right contents
    assert 'param' in pa_spec
    assert 'bin_edges' in pa_spec  # should be a list of floats
    assert 'sig_per_yr_binned' in pa_spec  # signal rate per bin (per year)
    # do the lengths of bin arrays match?
    assert len(pa_spec['bin_edges']) == len(pa_spec['sig_per_yr_binned']) + 1
    assert 'ref_bns_horizon' in pa_spec  # float
    assert 'netsnr_thresh' in pa_spec  # float

    return pa_spec


def read_template_bank_param(spec_data, bankf):
    """
    Parameters
    ----------
    spec_data: dictionary
        Prerequisite data for p astro calc
    bankf: string
        Path to HDF5 template bank file

    Returns
    -------
    bank_data: dictionary
        Template counts binned over specified param
    """
    bank = h5py.File(bankf, 'r')
    # All the templates
    tids = numpy.arange(len(bank['mass1']))
    # Get param vals
    logging.info('Getting %s values from bank', spec_data['param'])
    parvals = bankconv.get_bank_property(spec_data['param'], bank, tids)
    counts, edges = numpy.histogram(parvals, bins=spec_data['bin_edges'])
    bank_data = {'bin_edges': edges, 'tcounts': counts, 'num_t': counts.sum()}
    logging.info('Binned template counts:')
    logging.info(counts)

    return bank_data


def noise_density_from_far(far, exp_fac):
    """
    Exponential model of noise rate density per time per (reweighted) SNR
    b(rho) ~ k exp(-alpha * rho),
    where alpha is the 'index', yields the relation
    b(rho) = alpha * FAR(rho),
    where FAR is the integral of b(rho) from rho to infinity.
    E.g. fits to single-ifo noise typically yield alpha ~ 6
    """
    return exp_fac * far


def signal_pdf_from_snr(netsnr, thresh):
    """ FGMC approximate signal distribution ~ SNR ** -4
    """
    return numpy.exp(fgmcfun.log_rho_fg_analytic(netsnr, thresh))


def signal_rate_rescale(horizons, ref_dhor):
    """
    Compute a factor proportional to the rate of signals with given network SNR
    to account for network sensitivity variation relative to a reference state
    """
    # Combine sensitivities over ifos in a way analogous to network SNR
    net_horizon = sum(hor ** 2. for hor in horizons.values()) ** 0.5
    # signal rate is proportional to horizon distance cubed
    return net_horizon ** 3. / ref_dhor ** 3.


def template_param_bin_calc(padata, trdata, horizons):
    """
    Parameters
    ----------
    padata: PAstroData instance
        Static information on p astro calculation
    trdata: dictionary
        Trigger properties
    horizons: dictionary
        BNS horizon distances keyed on ifo

    Returns
    -------
    p_astro, p_terr: tuple of floats
    """
    massspin = (trdata['mass1'], trdata['mass2'],
                trdata['spin1z'], trdata['spin2z'])
    trig_param = triggers.get_param(padata.spec['param'], None, *massspin)
    # NB digitize gives '1' for first bin, '2' for second etc.
    bind = numpy.digitize(trig_param, padata.bank['bin_edges']) - 1
    logging.info('Trigger %s is in bin %i', padata.spec['param'], bind)

    # Get noise rate density
    if 'bg_fac' not in padata.spec:
        expfac = 6.
    else:
        expfac = padata.spec['bg_fac']
    print('Using exp factor ' + str(expfac))
    # FAR is in Hz, therefore convert to rate per year (per SNR)
    dnoise = noise_density_from_far(trdata['far'], expfac) * lal_s_per_yr
    logging.info('FAR %.3g, noise density per yr per SNR %.3g',
                 trdata['far'], dnoise)
    # Scale by fraction of templates in bin
    dnoise *= padata.bank['tcounts'][bind] / padata.bank['num_t']
    logging.info('Noise density in bin %.3g', dnoise)

    # Get signal rate density at given SNR
    dsig = signal_pdf_from_snr(trdata['network_snr'],
                               padata.spec['netsnr_thresh'])
    logging.info('SNR %.3g, signal pdf %.3g', trdata['network_snr'], dsig)
    dsig *= padata.spec['sig_per_yr_binned'][bind]
    logging.info('Signal density per yr per SNR in bin %.3g', dsig)
    # Scale by network sensitivity accounting for BNS horizon distances
    dsig *= signal_rate_rescale(horizons, padata.spec['ref_bns_horizon'])
    logging.info('After horizon rescaling %.3g', dsig)

    p_astro = dsig / (dsig + dnoise)
    logging.info('p_astro %.4g', p_astro)
    return p_astro, 1 - p_astro
