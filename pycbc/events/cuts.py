# Copyright (C) 2022 Gareth Cabourn Davies
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

"""
This module contains functions for reading in command line options and
applying cuts to triggers or templates in the offline search
"""
import logging
import numpy as np
from pycbc.events import ranking
from pycbc.io import hdf
from pycbc import conversions as conv
from pycbc.bank import conversions as bank_conv

sngl_rank_keys = ranking.sngls_ranking_function_dict.keys()

trigger_param_choices = ['end_time', 'psd_var_val', 'sigmasq']
trigger_param_choices += [cc + '_chisq' for cc in hdf.chisq_choices]
trigger_param_choices += sngl_rank_keys

template_fit_param_choices = ['fit_by_fit_coeff', 'smoothed_fit_coeff',
                              'fit_by_count_above_thresh',
                              'smoothed_fit_count_above_thresh',
                              'fit_by_count_in_template',
                              'smoothed_fit_count_in_template']
template_param_choices = bank_conv._conversion_options + \
                             template_fit_param_choices

ineq_choices = ['upper','lower','upper_inc','lower_inc']

# What are the inequalities associated with the cuts?
# 'upper' means upper limit, and so requires value < the threshold
ineq_functions = {
    'upper': np.less,
    'lower': np.greater,
    'upper_inc': np.less_equal,
    'lower_inc': np.greater_equal
}
def insert_cuts_option_group(parser):
    parser.add_argument('--trigger-cuts', nargs='+',
                        help="Cuts to apply to the triggers, supplied as "
                             "PARAMETER:VALUE:LIMIT, where, PARAMETER is the "
                             "parameter to be cut, VALUE is the value at "
                             "which it is cut, which must be convertible to "
                             "a float, and LIMIT is one of '"
                             + "', '".join(ineq_choices) +
                             "' to indicate the inequality needed. "
                             "PARAMETER is one of:'"
                             + "', '".join(trigger_param_choices) +
                             "'. For example snr:6:LOWER places the "
                             "requirement that matched filter SNR must be > 6")
    parser.add_argument('--template-cuts', nargs='+',
                        help="Cuts to apply to the triggers, supplied as "
                             "PARAMETER:VALUE:LIMIT. Format is the same as in "
                             "--trigger-cuts. PARAMETER can be one of '"
                             + "', '".join(template_param_choices) + "'.")

def ingest_cuts_option_group(args):
    """
    Check that the inputs given to options in insert_cuts_option_group
    are sensible, and return the objects used to handle the cuts.
    """
    # Deal with the case where no cuts are supplied:
    if not args.trigger_cuts and not args.template_cuts:
        return {}, {}

    # So that we can deal with the case where one set of cuts is supplied
    # but not the other, assign an empty list if no argument given
    trigger_cut_strs = args.trigger_cuts if args.trigger_cuts else []
    template_cut_strs = args.template_cuts if args.template_cuts else []

    # Check things in both cut sets
    for inputstr in trigger_cut_strs + template_cut_strs:
        _, cut_value_str, cut_limit = inputstr.split(':')
        if cut_limit.lower() not in ineq_choices:
            raise argparse.ArgparseError("Cut inequality not recognised, "
                                         "choose from "
                                         + ", ".join(ineq_choices))
        try:
            cut_value = float(cut_value_str)
        except ValueError as e:
            logging.warning("Cut value must be convertible into a float, "
                            "got {}".format(cut_value))
            raise e

    # Handle trigger cuts
    trigger_cut_dict = {}
    for inputstr in trigger_cut_strs:
        cut_param, cut_value_str, cut_limit = inputstr.split(':')
        if cut_param.lower() not in trigger_param_choices:
            raise argparse.ArgparseError("Cut inequality not recognised, "
                                         "choose from "
                                         + ", ".join(trigger_param_choices))
        trigger_cut_dict[cut_param] = (ineq_functions[cut_limit],
                                       float(cut_value_str))

    # Handle template cuts
    template_cut_dict = {}
    for inputstr in template_cut_strs:
        cut_param, cut_value_str, cut_limit = inputstr.split(':')
        if cut_param.lower() not in template_param_choices:
            raise argparse.ArgparseError("Cut inequality not recognised, "
                                         "choose from "
                                         + ", ".join(template_param_choices))
        template_cut_dict[cut_param] = (ineq_functions[cut_limit],
                                        float(cut_value_str))

    return trigger_cut_dict, template_cut_dict

def apply_trigger_cuts(triggers, trigger_cut_dict):
    """
    Calculate the parameter for the triggers, and then
    apply the cuts defined in template_cut_dict

    Parameters:
    -----------
    triggers:

    trigger_cut_dict: dictionary
        Dictionary with parameters as keys, and tuples of
        (cut_function, cut_threshold) as values
        made using ingest_cuts_option_group function

    Returns:
    --------
    """
    idx_out = np.arange(len(triggers['snr']))

    # Loop through the different cuts, and apply them
    for parameter, cut_function_thresh in trigger_cut_dict.items():
        # The function and threshold are stored as a tuple so unpack it
        cut_function, cut_thresh = cut_function_thresh

        # What is the value?
        if parameter.endswith('_chisq'):
            # parameter is a chisq-type thing
            chisq_choice = parameter.split('_')[0]
            value = get_chisq_from_file_choice(triggers, chisq_choice)
        elif parameter in triggers.file[triggers.ifo]:
            # parameter can be read direct from the trigger file
            value = triggers[parameter]
        elif parameter in sngl_rank_keys:
            # parameter is a newsnr-type thing
            value = ranking.get_sngls_ranking_from_trigs(triggers, parameter)
        else:
            raise NotImplementedError("Parameter '" + parameter + "' not "
                                      "recognised. Input sanitisation means "
                                      "this shouldn't have happened?!")

        idx_out = idx_out[cut_function(value, cut_thresh)]

    return idx_out



def apply_template_cuts(statistic, ifos, bank,
                        template_cut_dict, template_ids=None):
    """
    Fetch/calculate the parameter for the templates, possibly already
    preselected by template_ids, and then apply the cuts defined
    in template_cut_dict
    As this is used to select templates for use in findtrigs codes,
    we remove anything which does not pass

    Parameters:
    -----------
    statistic:
        A PyCBC ranking statistic instance. Used for the template fit
        cuts. If fits_by_tid does not exist for each ifo, then
        template fit cuts will be skipped. If a fit cut has been specified
        and fits_by_tid does not exist for all ifos, an error will be raised.

    ifos: list of strings
        List of IFOS used in this findtrigs instance.
        Templates must pass cuts in all IFOs. This is important
        e.g. for template fit parameter cuts.

    bank: h5py File object, or a dictionary
        Must contain the usual template bank datasets

    template_cut_dict: dictionary
        Dictionary with parameters as keys, and tuples of
        (cut_function, cut_threshold) as values
        made using ingest_cuts_option_group function

    Optional Parameters:
    --------------------
    template_ids: list of indices
        Indices of templates to consider within the bank, useful if
        templates have already been down-selected

    Returns:
    --------
    tids_out: numpy array
        Array of template_ids which have passed all cuts
    """
    # Get the initial list of templates:
    tids_out = np.arange(bank['mass1'].size) if template_ids is None else template_ids[:]

    # We can only apply template fit cuts if template fits have been done
    template_fit_cuts_allowed = hasattr(statistic, 'fits_by_tid')
    statistic_classname = statistic.__class__.__name__

    # Loop through the different cuts, and apply them
    for parameter, cut_function_thresh in template_cut_dict.items():
        # The function and threshold are stored as a tuple so unpack it
        cut_function, cut_thresh = cut_function_thresh

        if parameter in bank_conv._conversion_options:
            # Calculate the parameter values using the bank_conversion helper
            values = bank_conv.bank_conversion(parameter, bank, tids_out)
            # Only keep templates which pass this cut
            tids_out = tids_out[cut_function(values, cut_thresh)]
        elif parameter in template_fit_param_choices:
            if not template_fit_cuts_allowed:
                raise ValueError("Cut parameter " + parameter + " cannot "
                                 "be used when the ranking statistic " +
                                 statistic_classname + " does not use "
                                 "template fitting.")
            # Need to apply this cut to all IFOs
            for ifo in ifos:
                fits_dict = statistic.fits_by_tid[ifo]
                if parameter not in fits_dict:
                    raise ValueError("Cut parameter " + parameter + " not "
                                     "available in fits file.")
                values = fits_dict[parameter][tids_out]
                # Only keep templates which pass this cut
                tids_out = tids_out[cut_function(values, cut_thresh)]
        else:
            raise ValueError("Cut parameter " + parameter + " not recognised."
                             " This shouldn't happen with input sanitisation")

    logging.info("%d out of %d templates kept after applying template cuts",
                 len(tids_out), len(template_ids))

    return tids_out
