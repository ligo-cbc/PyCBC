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

"""Utilities for loading data for models.
"""

import logging
from argparse import ArgumentParser
import numpy

from pycbc.types import MultiDetOptionAction
from pycbc.psd import (insert_psd_option_group_multi_ifo,
                       from_cli_multi_ifos as psd_from_cli_multi_ifos,
                       verify_psd_options_multi_ifo)
from pycbc import strain
from pycbc.strain import from_cli_multi_ifos as strain_from_cli_multi_ifos
from pycbc.strain import (gates_from_cli, psd_gates_from_cli,
                          apply_gates_to_td, apply_gates_to_fd,
                          verify_strain_options_multi_ifo)
from pycbc import dq


#
# =============================================================================
#
#                   Utilities for gravitational-wave data
#
# =============================================================================
#
class NoValidDataError(Exception):
    """This should be raised if a continous segment of valid data could not be
    found.
    """
    pass

def create_data_parser():
    """Creates an argument parser for loading GW data."""
    parser = ArgumentParser()
    # add data options
    parser.add_argument("--instruments", type=str, nargs="+", required=True,
                        help="Instruments to analyze, eg. H1 L1.")
    parser.add_argument("--trigger-time", type=float, default=0.,
                        help="Reference GPS time (at geocenter) from which "
                             "the (anlaysis|psd)-(start|end)-time options are "
                             "measured. The integer seconds will be used. "
                             "Default is 0; i.e., if not provided, "
                             "the analysis and psd times should be in GPS "
                             "seconds.")
    parser.add_argument("--analysis-start-time", type=int, required=True,
                        nargs='+', action=MultiDetOptionAction,
                        metavar='IFO:TIME',
                        help="The start time to use for the analysis, "
                             "measured with respect to the trigger-time. "
                             "If psd-inverse-length is provided, the given "
                             "start time will be padded by half that length "
                             "to account for wrap-around effects.")
    parser.add_argument("--analysis-end-time", type=int, required=True,
                        nargs='+', action=MultiDetOptionAction,
                        metavar='IFO:TIME',
                        help="The end time to use for the analysis, "
                             "measured with respect to the trigger-time. "
                             "If psd-inverse-length is provided, the given "
                             "end time will be padded by half that length "
                             "to account for wrap-around effects.")
    parser.add_argument("--psd-start-time", type=int, default=None,
                        nargs='+', action=MultiDetOptionAction,
                        metavar='IFO:TIME',
                        help="Start time to use for PSD estimation, measured "
                             "with respect to the trigger-time.")
    parser.add_argument("--psd-end-time", type=int, default=None,
                        nargs='+', action=MultiDetOptionAction,
                        metavar='IFO:TIME',
                        help="End time to use for PSD estimation, measured "
                             "with respect to the trigger-time.")
    parser.add_argument("--data-conditioning-low-freq", type=float,
                        nargs="+", action=MultiDetOptionAction,
                        metavar='IFO:FLOW', dest="low_frequency_cutoff",
                        help="Low frequency cutoff of the data. Needed for "
                             "PSD estimation and when creating fake strain. "
                             "If not provided, will use the model's "
                             "low-frequency-cutoff.")
    insert_psd_option_group_multi_ifo(parser)
    strain.insert_strain_option_group_multi_ifo(parser, gps_times=False)
    strain.add_gate_option_group(parser)
    # add arguments for dq
    dqgroup = parser.add_argument_group("Options for quering data quality "
                                        "(DQ).")
    dqgroup.add_argument('--dq-segment-name', default='DATA',
                         help='The status flag to query for data quality. '
                              'Default is "DATA".')
    dqgroup.add_argument('--dq-source', choices=['any', 'GWOSC', 'dqsegdb'],
                         default='any',
                         help='Where to look for DQ information. If "any" '
                              '(the default) will first try GWOSC, then '
                              'dqsegdb.')
    dqgroup.add_argument('--dq-server', default='segments.ligo.org',
                         help='The server to use for dqsegdb.')
    dqgroup.add_argument('--veto-definer', default=None,
                         help='Path to a veto definer file that defines '
                              'groups of flags, which themselves define a set '
                              'of DQ segments.')
    return parser


def check_validtimes(detector, gps_start, gps_end, shift_to_valid=False,
                     max_shift=None, segment_name='DATA',
                     **kwargs):
    """Checks DQ server to see if the given times are in a valid segment.

    If the ``shift_to_valid`` flag is provided, the times will be shifted left
    or right to try to find a continous valid block nearby. The shifting starts
    by shifting the times left by 1 second. If that does not work, it shifts
    the times right by one second. This continues, increasing the shift time by
    1 second, until a valid block could be found, or until the shift size
    exceeds ``max_shift``.

    If the given times are not in a continuous valid segment, or a valid block
    cannot be found nearby, a ``NoValidDataError`` is raised.

    Parameters
    ----------
    detector : str
        The name of the detector to query; e.g., 'H1'.
    gps_start : int
        The GPS start time of the segment to query.
    gps_end : int
        The GPS end time of the segment to query.
    shift_to_valid : bool, optional
        If True, will try to shift the gps start and end times to the nearest
        continous valid segment of data. Default is False.
    max_shift : int, optional
        The maximum number of seconds to try to shift left or right to find
        a valid segment. Default is ``gps_end - gps_start``.
    segment_name : str, optional
        The status flag to query; passed to :py:func:`pycbc.dq.query_flag`.
        Default is "DATA".
    \**kwargs :
        All other keyword arguments are passed to
        :py:func:`pycbc.dq.query_flag`.

    Returns
    -------
    use_start : int
        The start time to use. If ``shift_to_valid`` is True, this may differ
        from the given GPS start time.
    use_end : int
        The end time to use. If ``shift_to_valid`` is True, this may differ
        from the given GPS end time.
    """
    # expand the times checked encase we need to shift
    if max_shift is None:
        max_shift = int(gps_end - gps_start)
    check_start = gps_start - max_shift
    check_end = gps_end + max_shift
    validsegs = dq.query_flag(detector, segment_name, check_start, check_end,
                              **kwargs)
    use_start = gps_start
    use_end = gps_end
    # shift if necessary
    if shift_to_valid:
        shiftsize = 1
        while (use_start, use_end) not in validsegs and shiftsize < max_shift:
            # try shifting left
            use_start = gps_start - shiftsize
            use_end = gps_end - shiftsize
            if (use_start, use_end) not in validsegs:
                # try shifting right
                use_start = gps_start + shiftsize
                use_end = gps_end + shiftsize
            shiftsize += 1
    # check that we have a valid range
    if (use_start, use_end) not in validsegs:
        raise NoValidDataError("Could not find a continous valid segment in "
                               "in detector {}".format(detector))
    return use_start, use_end


def data_opts_from_config(cp, section, filter_flow):
    """Loads data options from a section in a config file.

    Parameters
    ----------
    cp : WorkflowConfigParser
        Config file to read.
    section : str
        The section to read. All options in the section will be loaded as-if
        they wre command-line arguments.
    filter_flow : dict
        Dictionary of detectors -> inner product low frequency cutoffs.
        If a `data-conditioning-low-freq` cutoff wasn't provided for any
        of the detectors, these values will be used. Otherwise, the
        data-conditioning-low-freq must be less than the inner product cutoffs.
        If any are not, a ``ValueError`` is raised.

    Returns
    -------
    opts : parsed argparse.ArgumentParser
        An argument parser namespace that was constructed as if the options
        were specified on the command line.
    """
    # convert the section options into a command-line options
    optstr = cp.section_to_cli(section)
    # create a fake parser to parse them
    parser = create_data_parser()
    # parse the options
    opts = parser.parse_args(optstr.split())
    # figure out the times to use
    logging.info("Determining analysis times to use")
    opts.trigger_time = int(opts.trigger_time)
    gps_start = opts.analysis_start_time.copy()
    gps_end = opts.analysis_end_time.copy()
    for det in opts.instruments:
        gps_start[det] += opts.trigger_time
        gps_end[det] += opts.trigger_time
        if opts.psd_inverse_length is not None:
            pad = int(numpy.ceil(opts.psd_inverse_length[det] / 2))
            logging.info("Padding {} analysis start and end times by {} "
                         "(= psd-inverse-length/2) seconds to "
                         "account for PSD wrap around effects."
                         .format(det, pad))
        gps_start[det] -= pad
        gps_end[det] += pad
        if opts.psd_start_time is not None:
            opts.psd_start_time[det] += opts.trigger_time
        if opts.psd_end_time is not None:
            opts.psd_end_time[det] += opts.trigger_time
    opts.gps_start_time = gps_start
    opts.gps_end_time = gps_end
    # check for the frequencies
    low_freq_cutoff = filter_flow.copy()
    if opts.low_frequency_cutoff:
        # add in any missing detectors
        low_freq_cutoff.update({det: opts.low_frequency_cutoff[det]
                                for det in opts.instruments
                                if opts.low_frequency_cutoff[det] is not None})
        # make sure the data conditioning low frequency cutoff is < than
        # the matched filter cutoff
        if any(low_freq_cutoff[det] > filter_flow[det] for det in filter_flow):
            raise ValueError("data conditioning low frequency cutoff must "
                             "be less than the filter low frequency "
                             "cutoff")
    # have to clear to remove the random string thing in DictWithDefaultReturn
    opts.low_frequency_cutoff.clear()
    opts.low_frequency_cutoff.update(low_freq_cutoff)
    # verify options are sane
    verify_psd_options_multi_ifo(opts, parser, opts.instruments)
    verify_strain_options_multi_ifo(opts, parser, opts.instruments)
    return opts


def data_from_cli(opts, check_for_valid_times=True,
                  shift_psd_times_to_valid=True,
                  err_on_missing_detectors=False):
    """Loads the data needed for a model from the given command-line options.

    Gates specifed on the command line are also applied.

    Parameters
    ----------
    opts : ArgumentParser parsed args
        Argument options parsed from a command line string (the sort of thing
        returned by `parser.parse_args`).
    check_for_valid_times : bool, optional
        Check that valid data exists in the requested gps times. Default is
        True.
    shift_psd_times_to_valid : bool, optional
        If estimating the PSD from data, shift the PSD times to a valid
        segment if needed. Default is True.
    err_on_missing_detectors : bool, optional
        Raise a NoValidDataError if any detector does not have valid data.
        Otherwise, a warning is printed, and that detector is skipped.

    Returns
    -------
    strain_dict : dict
        Dictionary of instruments -> `TimeSeries` strain.
    stilde_dict : dict
        Dictionary of instruments -> `FrequencySeries` strain.
    psd_dict : dict
        Dictionary of instruments -> `FrequencySeries` psds.
    """
    # get gates to apply
    gates = gates_from_cli(opts)
    psd_gates = psd_gates_from_cli(opts)

    # get strain time series
    instruments = opts.instruments

    # validate times
    if check_for_valid_times:
        dets_with_data = []
        for det in instruments:
            logging.info("Checking that {} has valid data in the requested "
                         "analysis times".format(det))
            try:
                check_validtimes(det, opts.gps_start_time[det],
                                 opts.gps_end_time[det],
                                 shift_to_valid=False,
                                 segment_name=opts.dq_segment_name,
                                 source=opts.dq_source,
                                 server=opts.dq_server,
                                 veto_definer=opts.veto_definer)
                dets_with_data.append(det)
            except NoValidDataError as e:
                if err_on_missing_detectors:
                    raise NoValidDataError(e)
                else:
                    logging.warn("WARNING: Detector {} will not be used in "
                                 "the analysis, as it does not have "
                                 "continuous valid data that spans the "
                                 "anlysis segment [{}, {})."
                                 .format(det, opts.gps_start_time[det],
                                         opts.gps_end_time[det]))
                    pass
        instruments = dets_with_data

    strain_dict = strain_from_cli_multi_ifos(opts, instruments,
                                             precision="double")
    # apply gates if not waiting to overwhiten
    if not opts.gate_overwhitened:
        strain_dict = apply_gates_to_td(strain_dict, gates)

    # get strain time series to use for PSD estimation
    # if user has not given the PSD time options then use same data as analysis
    if opts.psd_start_time and opts.psd_end_time:
        logging.info("Will generate a different time series for PSD "
                     "estimation")
        if check_for_valid_times:
            psd_times = {}
            dets_with_data = []
            for det in instruments:
                logging.info("Checking that {} has valid data in requested "
                             "times for PSD estimation".format(det))
                try:
                    psd_start, psd_end = check_validtimes(
                        det, opts.psd_start_time[det],
                        opts.psd_end_time[det],
                        shift_to_valid=shift_psd_times_to_valid,
                        segment_name=opts.dq_segment_name,
                        source=opts.dq_source,
                        server=opts.dq_server,
                        veto_definer=opts.veto_definer)
                    psd_times[det] = (psd_start, psd_end)
                    dets_with_data.append(det)
                except NoValidDataError as e:
                    if err_on_missing_detectors:
                        raise NoValidDataError(e)
                    else:
                        logging.warn("WARNING: Detector {} will not be used "
                                     "in the analysis, as enough valid data "
                                     "could not be found to estimate the PSD."
                                     .format(det))
                        strain_dict.pop(det)
                        pass
            instruments = dets_with_data
        else:
            psd_times = {det: (opts.psd_start_time, opts.psd_end_time)
                         for det in instruments}
        psd_strain_dict = {}
        for det, (psd_start, psd_end) in psd_times.items():
            #psd_opts = opts
            opts.gps_start_time = psd_start
            opts.gps_end_time = psd_end
            psd_strain_dict.update(
                strain_from_cli_multi_ifos(opts, [det], precision="double"))
        # apply any gates
        logging.info("Applying gates to PSD data")
        psd_strain_dict = apply_gates_to_td(psd_strain_dict, psd_gates)

    elif opts.psd_start_time or opts.psd_end_time:
        raise ValueError("Must give psd-start-time and psd-end-time")
    else:
        psd_strain_dict = strain_dict

    # check that we have data left to analyze
    if instruments == []:
        raise NoValidDataError("No valid data could be found in any of the "
                               "requested instruments.")

    # FFT strain and save each of the length of the FFT, delta_f, and
    # low frequency cutoff to a dict
    stilde_dict = {}
    length_dict = {}
    delta_f_dict = {}
    for ifo in instruments:
        stilde_dict[ifo] = strain_dict[ifo].to_frequencyseries()
        length_dict[ifo] = len(stilde_dict[ifo])
        delta_f_dict[ifo] = stilde_dict[ifo].delta_f

    # get PSD as frequency series
    psd_dict = psd_from_cli_multi_ifos(
        opts, length_dict, delta_f_dict, opts.low_frequency_cutoff,
        instruments, strain_dict=psd_strain_dict, precision="double")

    # apply any gates to overwhitened data, if desired
    if opts.gate_overwhitened and opts.gate is not None:
        logging.info("Applying gates to overwhitened data")
        # overwhiten the data
        for ifo in gates:
            stilde_dict[ifo] /= psd_dict[ifo]
        stilde_dict = apply_gates_to_fd(stilde_dict, gates)
        # unwhiten the data for the model
        for ifo in gates:
            stilde_dict[ifo] *= psd_dict[ifo]

    return strain_dict, stilde_dict, psd_dict


