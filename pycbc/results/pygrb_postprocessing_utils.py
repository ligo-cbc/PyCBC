# Copyright (C) 2019 Francesco Pannarale, Gino Contestabile, Cameron Mills
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


# =============================================================================
# Preamble
# =============================================================================

"""
Module to generate PyGRB figures: scatter plots and timeseries.
"""

import sys
import glob
import os
import logging
import argparse
import copy
import numpy
from scipy import stats
from pycbc.detector import Detector
# TODO: imports to fix/remove
try:
    from ligo import segments
    from ligo.lw import utils, lsctables, ligolw, table
    from ligo.segments.utils import fromsegwizard
except ImportError:
    pass
try:
    from pylal import MultiInspiralUtils
except ImportError:
    pass


# =============================================================================
# Arguments functions:
# * Initialize a parser object with arguments shared by all plotting scripts
# * Add to the parser object the arguments used for Monte-Carlo on distance
# * Add to the parser object the arguments used for BestNR calculation
# * Add to the parser object the arguments for found/missed injection files
# =============================================================================
# TODO: move to plotting_utils and do not use in non-plot executables
# TODO: make required once pygrb_efficiency no longer uses this
def pygrb_initialize_plot_parser(usage='', description=None, version=None):
    """Sets up a basic argument parser object for PyGRB plotting scripts"""

    parser = argparse.ArgumentParser(usage=usage, description=description,
                                     formatter_class=
                                     argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--version", action="version", version=version)
    parser.add_argument("-v", "--verbose", default=False, action="store_true",
                        help="Verbose output")
    parser.add_argument("-o", "--output-file", default=None,
                        help="Output file.")
    parser.add_argument("--x-lims", action="store", default=None,
                        help="Comma separated minimum and maximum values " +
                        "for the horizontal axis. When using negative " +
                        "values an equal sign after --x-lims is necessary.")
    parser.add_argument("--y-lims", action="store", default=None,
                        help="Comma separated minimum and maximum values " +
                        "for the vertical axis. When using negative values " +
                        "an equal sign after --y-lims is necessary.")
    parser.add_argument("--use-logs", default=False, action="store_true",
                        help="Produce a log-log plot")
    parser.add_argument("-i", "--ifo", default=None, help="IFO used for IFO " +
                        "specific plots")
    parser.add_argument("-I", "--inj-file", action="store", default=None,
                        help="The location of the injection file")
    parser.add_argument("-a", "--segment-dir", action="store",
                        required=True, help="Directory holding buffer, on " +
                        "and off source segment files.")
    parser.add_argument("-l", "--veto-directory", action="store", default=None,
                        help="The location of the CATX veto files")
    parser.add_argument("-b", "--veto-category", action="store", type=int,
                        default=None, help="Apply vetoes up to this level " +
                        "inclusive.")
    parser.add_argument('--plot-title', default=None,
                        help="If provided, use the given string as the plot " +
                        "title.")
    parser.add_argument('--plot-caption', default=None,
                        help="If provided, use the given string as the plot " +
                        "caption")

    return parser


def pygrb_add_injmc_opts(parser):
    """Add to parser object the arguments used for Monte-Carlo on distance."""
    if parser is None:
        parser = argparse.ArgumentParser()
    parser.add_argument("-M", "--num-mc-injections", action="store",
                        type=int, default=100, help="Number of Monte " +
                        "Carlo injection simulations to perform.")
    parser.add_argument("-S", "--seed", action="store", type=int,
                        default=1234, help="Seed to initialize Monte Carlo.")
    parser.add_argument("-U", "--upper-inj-dist", action="store",
                        type=float, default=1000, help="The upper distance " +
                        "of the injections in Mpc, if used.")
    parser.add_argument("-L", "--lower-inj-dist", action="store",
                        type=float, default=0, help="The lower distance of " +
                        "the injections in Mpc, if used.")
    parser.add_argument("-n", "--num-bins", action="store", type=int,
                        default=0, help="The number of bins used to " +
                        "calculate injection efficiency.")
    parser.add_argument("-w", "--waveform-error", action="store",
                        type=float, default=0, help="The standard deviation " +
                        "to use when calculating the waveform error.")
    parser.add_argument("--h1-cal-error", action="store", type=float,
                        default=0, help="The standard deviation to use when " +
                        "calculating the H1 calibration amplitude error.")
    parser.add_argument("--k1-cal-error", action="store", type=float,
                        default=0, help="The standard deviation to use when " +
                        "calculating the K1 calibration amplitude error.")
    parser.add_argument("--l1-cal-error", action="store", type=float,
                        default=0, help="The standard deviation to use when " +
                        "calculating the L1 calibration amplitude error.")
    parser.add_argument("--v1-cal-error", action="store", type=float,
                        default=0, help="The standard deviation to use when " +
                        "calculating the V1 calibration amplitude error.")
    parser.add_argument("--h1-dc-cal-error", action="store",
                        type=float, default=1.0, help="The scaling factor " +
                        "to use when calculating the H1 calibration " +
                        "amplitude error.")
    parser.add_argument("--k1-dc-cal-error", action="store",
                        type=float, default=1.0, help="The scaling factor " +
                        "to use when calculating the K1 calibration " +
                        "amplitude error.")
    parser.add_argument("--l1-dc-cal-error", action="store",
                        type=float, default=1.0, help="The scaling factor " +
                        "to use when calculating the L1 calibration " +
                        "amplitude error.")
    parser.add_argument("--v1-dc-cal-error", action="store",
                        type=float, default=1.0, help="The scaling factor " +
                        "to use when calculating the V1 calibration " +
                        "amplitude error.")

    return parser


def pygrb_add_bestnr_opts(parser):
    """Add to the parser object the arguments used for BestNR calculation."""
    if parser is None:
        parser = argparse.ArgumentParser()
    parser.add_argument("-Q", "--chisq-index", action="store", type=float,
                        default=4.0, help="chisq_index for newSNR calculation")
    parser.add_argument("-N", "--chisq-nhigh", action="store", type=float,
                        default=3.0, help="nhigh for newSNR calculation")
    parser.add_argument("-B", "--sngl-snr-threshold", action="store",
                        type=float, default=4.0, help="Single detector SNR " +
                        "threshold, the two most sensitive detectors " +
                        "should have SNR above this.")
    parser.add_argument("-d", "--snr-threshold", action="store", type=float,
                        default=6.0, help="SNR threshold for recording " +
                        "triggers.")
    parser.add_argument("-c", "--newsnr-threshold", action="store", type=float,
                        default=None, help="NewSNR threshold for " +
                        "calculating the chisq of triggers (based on value " +
                        "of auto and bank chisq  values. By default will " +
                        "take the same value as snr-threshold.")
    parser.add_argument("-A", "--null-snr-threshold", action="store",
                        default="4.25,6",
                        help="Comma separated lower,higher null SNR " +
                        "threshold for null SNR cut")
    parser.add_argument("-T", "--null-grad-thresh", action="store", type=float,
                        default=20., help="Threshold above which to " +
                        "increase the values of the null SNR cut")
    parser.add_argument("-D", "--null-grad-val", action="store", type=float,
                        default=0.2, help="Rate the null SNR cut will " +
                        "increase above the threshold")

    return parser


def pygrb_add_fminjs_input_opts(parser):
    """Add to parser object the arguments for found/missed injection files."""
    if parser is None:
        parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--found-file", action="store",
                        default=None,
                        help="Location of the found injections file")
    parser.add_argument("-m", "--missed-file", action="store",
                        default=None,
                        help="Location of the missed injections file")

    return parser


# =============================================================================
# Wrapper to read segments files
# =============================================================================
def read_seg_files(seg_dir):
    """Given the segments directory, read segments files"""

    times = {}
    keys = ["buffer", "off", "on"]
    file_names = ["bufferSeg.txt", "offSourceSeg.txt", "onSourceSeg.txt"]

    for key, file_name in zip(keys, file_names):
        segs = fromsegwizard(open(os.path.join(seg_dir, file_name), 'r'))
        if len(segs) > 1:
            logging.error('More than one segment, an error has occured.')
            sys.exit()
        times[key] = segs[0]

    return times


# =============================================================================
# Function to load a table from an xml file
# =============================================================================
def load_xml_table(file_name, table_name):
    """Load xml table from file."""

    xml_doc = utils.load_filename(file_name, gz=file_name.endswith("gz"),
                                  contenthandler=lsctables.use_in(
                                      ligolw.LIGOLWContentHandler))

    return table.get_table(xml_doc, table_name)


# ==============================================================================
# Function to load segments from an xml file
# ==============================================================================
def load_segments_from_xml(xml_doc, return_dict=False, select_id=None):
    """Read a ligo.segments.segmentlist from the file object file containing an
    xml segment table.

    Parameters
    ----------
        xml_doc: name of segment xml file

        Keyword Arguments:
            return_dict : [ True | False ]
                return a ligo.segments.segmentlistdict containing coalesced
                ligo.segments.segmentlists keyed by seg_def.name for each entry
                in the contained segment_def_table. Default False
            select_id : int
                return a ligo.segments.segmentlist object containing only
                those segments matching the given segment_def_id integer

    """

    # Load SegmentDefTable and SegmentTable
    seg_def_table = load_xml_table(xml_doc,
                                   lsctables.SegmentDefTable.tableName)
    seg_table = load_xml_table(xml_doc, lsctables.SegmentTable.tableName)

    if return_dict:
        segs = segments.segmentlistdict()
    else:
        segs = segments.segmentlist()

    seg_id = {}
    for seg_def in seg_def_table:
        seg_id[int(seg_def.segment_def_id)] = str(seg_def.name)
        if return_dict:
            segs[str(seg_def.name)] = segments.segmentlist()

    for seg in seg_table:
        if return_dict:
            segs[seg_id[int(seg.segment_def_id)]]\
                .append(segments.segment(seg.start_time, seg.end_time))
            continue
        if select_id and int(seg.segment_def_id) == select_id:
            segs.append(segments.segment(seg.start_time, seg.end_time))
            continue
        segs.append(segments.segment(seg.start_time, seg.end_time))

    if return_dict:
        for seg_name in seg_id.values():
            segs[seg_name] = segs[seg_name].coalesce()
    else:
        segs = segs.coalesce()

    return segs


# =============================================================================
# Function to extract vetoes
# =============================================================================
def extract_vetoes(veto_files, ifos):
    """Extracts vetoes from veto filelist"""

    # Initialize veto containers
    vetoes = segments.segmentlistdict()
    for ifo in ifos:
        vetoes[ifo] = segments.segmentlist()

    # Construct veto list from veto filelist
    if veto_files:
        for veto_file in veto_files:
            ifo = os.path.basename(veto_file)[:2]
            if ifo in ifos:
                # This returns a coalesced list of the vetoes
                tmp_veto_segs = load_segments_from_xml(veto_file)
                for entry in tmp_veto_segs:
                    vetoes[ifo].append(entry)
    for ifo in ifos:
        vetoes[ifo].coalesce()

    return vetoes


# =============================================================================
# Function to get the ID numbers from a LIGO-LW table
# =============================================================================
def get_id_numbers(ligolw_table, column):
    """Grab the IDs of a LIGO-LW table"""

    ids = [int(getattr(row, column)) for row in ligolw_table]

    return ids


#
# Used (also) in executables
#

# =============================================================================
# Function to load triggers
# =============================================================================
def load_triggers(trig_file, vetoes):
    """Loads triggers from PyGRB output file"""

    logging.info("Loading triggers...")

    # Determine ifos
    ifos = vetoes.keys()

    # Extract time-slides
    multis, slide_dict, _ = \
        MultiInspiralUtils.ReadMultiInspiralTimeSlidesFromFiles([trig_file])
    num_slides = len(slide_dict)
    lsctables.MultiInspiralTable.loadcolumns =\
        [slot for slot in multis[0].__slots__ if hasattr(multis[0], slot)]

    # Extract triggers
    trigs = lsctables.New(lsctables.MultiInspiralTable,
                          columns=lsctables.MultiInspiralTable.loadcolumns)
    logging.info("%d triggers found.", len(trigs))

    # Time-slid vetoes
    for slide_id in range(num_slides):
        slid_vetoes = copy.deepcopy(vetoes)
        for ifo in ifos:
            slid_vetoes[ifo].shift(-slide_dict[slide_id][ifo])

        # Add time-slid triggers
        vets = slid_vetoes.union(slid_vetoes.keys())
        trigs.extend(t for t in multis.veto(vets)
                     if int(t.time_slide_id) == slide_id)

    logging.info("%d triggers found when including timeslides.", len(trigs))

    return trigs


# =============================================================================
# Detector utils:
# * Function to calculate the antenna factors F+ and Fx
# * Function to calculate the antenna response F+^2 + Fx^2
# * Function to calculate the antenna distance factor
# =============================================================================
# TODO: the call, e.g., Detector("H1", reference_time=None) will not always
# work because we are on Python 2.7 and therefore on an old version of astropy
# which cannot download recent enough IERS tables. TEMPORARILY use the
# default time (GW150914) as reference, thus approximating the sidereal time.
# TODO: would getting rid of get_antenna_factors slow things down?
#       It is used only in here.
def get_antenna_factors(antenna, ra, dec, geocent_time):
    """Returns the antenna responses F+ and Fx of an IFO (passed as pycbc
    Detector type) at a given sky location and time."""

    f_plus, f_cross = antenna.antenna_pattern(ra, dec, 0, geocent_time)

    return f_plus, f_cross


def get_antenna_single_response(antenna, ra, dec, geocent_time):
    """Returns the antenna response F+^2 + Fx^2 of an IFO (passed as pycbc
    Detector type) at a given sky location and time."""

    fp, fc = get_antenna_factors(antenna, ra, dec, geocent_time)

    return fp**2 + fc**2


# Vectorize the function above on all but the first argument
get_antenna_responses = numpy.vectorize(get_antenna_single_response,
                                        otypes=[float])
get_antenna_responses.excluded.add(0)


def get_antenna_dist_factor(antenna, ra, dec, geocent_time, inc=0.0):
    """Returns the antenna factors (defined as eq. 4.3 on page 57 of
    Duncan Brown's Ph.D.) for an IFO (passed as pycbc Detector type) at
    a given sky location and time."""

    fp, fc = get_antenna_factors(antenna, ra, dec, geocent_time)

    return numpy.sqrt(fp ** 2 * (1 + numpy.cos(inc)) ** 2 / 4 + fc ** 2)


# =============================================================================
# Function to calculate the detection statistic of a list of triggers
# TODO: where is the null SNR cut? get_bestnr reweights the SNR by null SNR
# (null_thresh[0], really): where is null_thresh[1] used?
# =============================================================================
def get_bestnrs(trigs, q=4.0, n=3.0, null_thresh=(4.25, 6), snr_threshold=6.,
                sngl_snr_threshold=4., chisq_threshold=None,
                null_grad_thresh=20., null_grad_val=0.2):
    """Calculate BestNR (coh_PTF detection statistic) of triggers through
    signal based vetoes.  The (default) signal based vetoes are:
    * Coherent SNR < 6
    * Bank chi-squared reduced (new) SNR < 6
    * Auto veto reduced (new) SNR < 6
    * Single-detector SNR (from two most sensitive IFOs) < 4
    * Null SNR (CoincSNR^2 - CohSNR^2)^(1/2) < null_thresh

    Returns Numpy array of BestNR values.
    """

    if not trigs:
        return numpy.array([])

    # Grab sky position and timing
    ra = trigs.get_column('ra')
    dec = trigs.get_column('dec')
    time = trigs.get_end()

    # Initialize BestNRs
    snr = trigs.get_column('snr')
    bestnr = numpy.ones(len(snr))

    # Coherent SNR cut
    bestnr[numpy.asarray(snr) < snr_threshold] = 0

    # Bank and auto chi-squared cuts
    if not chisq_threshold:
        chisq_threshold = snr_threshold
    bestnr[numpy.asarray(trigs.get_new_snr(index=q, nhigh=n,
                                           column='bank_chisq'))
           < chisq_threshold] = 0
    bestnr[numpy.asarray(trigs.get_new_snr(index=q, nhigh=n,
                                           column='cont_chisq'))
           < chisq_threshold] = 0

    # Define IFOs for sngl cut
    ifos = map(str, trigs[0].get_ifos())

    # Single detector SNR cut
    sens = {}
    sigmasqs = trigs.get_sigmasqs()
    ifo_snr = dict((ifo, trigs.get_sngl_snr(ifo)) for ifo in ifos)
    for ifo in ifos:
        antenna = Detector(ifo)
        sens[ifo] = sigmasqs[ifo] * get_antenna_responses(antenna, ra,
                                                          dec, time)
    for i_trig, trig in enumerate(trigs):
        # Apply only to triggers that were not already cut previously
        if bestnr[i_trig] != 0:
            ifos.sort(key=lambda ifo, j=i_trig: sens[ifo][j], reverse=True)
            # Apply when there is more than 1 IFO
            if len(ifos) > 1:
                for i in range(0, 2):
                    if ifo_snr[ifos[i]][i_trig] < sngl_snr_threshold:
                        bestnr[i_trig] = 0
        # Get chisq reduced (new) SNR for triggers that were not cut so far
        # NOTE: .get_bestnr is in ligo.lw.lsctables.MultiInspiralTable
        if bestnr[i_trig] != 0:
            bestnr[i_trig] = trig.get_bestnr(index=q, nhigh=n,
                                             null_snr_threshold=null_thresh[0],
                                             null_grad_thresh=null_grad_thresh,
                                             null_grad_val=null_grad_val)
        # If we got this far and the bestNR is non-zero, verify that chisq was
        # actually calculated for the trigger, otherwise print debugging info
        if bestnr[i_trig] != 0:
            if trig.chisq == 0:
                err_msg = "Chisq not calculated for trigger with end time "
                err_msg += "%s and snr %s" % (trig.get_end(), trig.snr)
                logging.error(err_msg)
                sys.exit()

    return bestnr


# =============================================================================
# Construct sorted triggers from trials
# =============================================================================
def sort_trigs(trial_dict, trigs, num_slides, seg_dict):
    """Constructs sorted triggers from a trials dictionary"""

    sorted_trigs = {}

    # Begin by sorting the triggers into each slide
    # New seems pretty slow, so run it once and then use deepcopy
    tmp_table = lsctables.New(lsctables.MultiInspiralTable)
    for slide_id in range(num_slides):
        sorted_trigs[slide_id] = copy.deepcopy(tmp_table)
    for trig in trigs:
        sorted_trigs[int(trig.time_slide_id)].append(trig)

    for slide_id in range(num_slides):
        # These can only *reduce* the analysis time
        curr_seg_list = seg_dict[slide_id]

        # TODO: below is a check we can possibly remove
        # Check the triggers are all in the analysed segment lists
        for trig in sorted_trigs[slide_id]:
            if trig.end_time not in curr_seg_list:
                # This can be raised if the trigger is on the segment boundary,
                # so check if the trigger is within 1/100 of a second within
                # the list
                if trig.get_end() + 0.01 in curr_seg_list:
                    continue
                if trig.get_end() - 0.01 in curr_seg_list:
                    continue
                err_msg = "Triggers found in input files not in the list of "
                err_msg += "analysed segments. This should not happen."
                logging.error(err_msg)
                sys.exit()
        # END OF CHECK #

        # The below line works like the inverse of .veto and only returns trigs
        # that are within the segment specified by trial_dict[slide_id]
        sorted_trigs[slide_id] = sorted_trigs[slide_id].\
                                 vetoed(trial_dict[slide_id])

    return sorted_trigs


# =============================================================================
# Extract basic trigger properties and store them as dictionaries
# TODO: the for's can be made more Pythonic probably.
# TODO: use argument to determine which properties to calculate?
# =============================================================================
def extract_basic_trig_properties(trial_dict, trigs, num_slides, seg_dict,
                                  opts):
    """Extract and store as dictionaries time, SNR, and BestNR of
    time-slid triggers"""

    # Sort the triggers into each slide
    sorted_trigs = sort_trigs(trial_dict, trigs, num_slides, seg_dict)
    logging.info("Triggers sorted.")

    # Local copies of variables entering the BestNR definition
    # TODO: does this slow  things down?
    chisq_index = opts.chisq_index
    chisq_nhigh = opts.chisq_nhigh
    null_thresh = map(float, opts.null_snr_threshold.split(','))
    snr_thresh = opts.snr_threshold
    sngl_snr_thresh = opts.sngl_snr_threshold
    new_snr_thresh = opts.newsnr_threshold
    null_grad_thresh = opts.null_grad_thresh
    null_grad_val = opts.null_grad_val

    # Build the 3 dictionaries
    trig_time = {}
    trig_snr = {}
    trig_bestnr = {}
    for slide_id in range(num_slides):
        slide_trigs = sorted_trigs[slide_id]
        if slide_trigs:
            trig_time[slide_id] = numpy.asarray(slide_trigs.get_end()).\
                                  astype(float)
            trig_snr[slide_id] = numpy.asarray(slide_trigs.get_column('snr'))
        else:
            trig_time[slide_id] = numpy.asarray([])
            trig_snr[slide_id] = numpy.asarray([])
        trig_bestnr[slide_id] = get_bestnrs(slide_trigs,
                                            q=chisq_index,
                                            n=chisq_nhigh,
                                            null_thresh=null_thresh,
                                            snr_threshold=snr_thresh,
                                            sngl_snr_threshold=sngl_snr_thresh,
                                            chisq_threshold=new_snr_thresh,
                                            null_grad_thresh=null_grad_thresh,
                                            null_grad_val=null_grad_val)
    logging.info("Time, SNR, and BestNR of triggers extracted.")

    return trig_time, trig_snr, trig_bestnr


# =============================================================================
# Find GRB trigger time
# =============================================================================
def get_grb_time(seg_dir):
    """Determine GRB trigger time"""

    segs = read_seg_files(seg_dir)
    grb_time = segs['on'][1] - 1

    return grb_time


# =============================================================================
# Function to extract ifos
# =============================================================================
def extract_ifos(trig_file):
    """Extracts IFOs from search summary table"""

    # Load search summary
    search_summ = load_xml_table(trig_file,
                                 lsctables.SearchSummaryTable.tableName)

    # Extract IFOs
    ifos = sorted(map(str, search_summ[0].get_ifos()))

    return ifos


# =============================================================================
# Function to extract IFOs and vetoes
# =============================================================================
def extract_ifos_and_vetoes(trig_file, veto_dir, veto_cat):
    """Extracts IFOs from search summary table and vetoes from a directory"""

    logging.info("Extracting IFOs and vetoes.")

    # Extract IFOs
    ifos = extract_ifos(trig_file)

    # Extract vetoes
    veto_files = []
    if veto_dir:
        veto_string = ','.join([str(i) for i in range(2, veto_cat+1)])
        veto_files = glob.glob(veto_dir + '/*CAT[%s]*.xml' % (veto_string))
    vetoes = extract_vetoes(veto_files, ifos)

    return ifos, vetoes


# =============================================================================
# Function to load injections
# =============================================================================
def load_injections(inj_file, vetoes, sim_table=False, label=None):
    """Loads injections from PyGRB output file"""

    if label is None:
        logging.info("Loading injections...")
    else:
        logging.info("Loading %s...", label)

    insp_table = lsctables.MultiInspiralTable
    if sim_table:
        insp_table = lsctables.SimInspiralTable

    # Load injections in injection file
    inj_table = load_xml_table(inj_file, insp_table.tableName)

    # Extract injections in time-slid non-vetoed data
    injs = lsctables.New(insp_table, columns=insp_table.loadcolumns)
    injs.extend(inj for inj in inj_table if inj.get_end() not in vetoes)

    if label is None:
        logging.info("%d injections found.", len(injs))
    else:
        logging.info("%d %s found.", len(injs), label)

    return injs


# =============================================================================
# Function to load timeslides
# TODO: can this be made local?
# =============================================================================
def load_time_slides(xml_file):
    """Loads timeslides from PyGRB output file"""

    time_slide = load_xml_table(xml_file, lsctables.TimeSlideTable.tableName)
    time_slide_unsorted = [dict(i) for i in time_slide.as_dict().values()]
    # NB: sorting not necessary if using python 3
    sort_idx = numpy.argsort(numpy.array([
        int(time_slide.get_time_slide_id(ov)) for ov in time_slide_unsorted
    ]))
    time_slide_list = numpy.array(time_slide_unsorted)[sort_idx]
    # Check time_slide_ids are ordered correctly.
    ids = get_id_numbers(time_slide,
                         "time_slide_id")[::len(time_slide_list[0].keys())]
    if not (numpy.all(ids[1:] == numpy.array(ids[:-1])+1) and ids[0] == 0):
        err_msg = "time_slide_ids list should start at zero and increase by "
        err_msg += "one for every element"
        logging.error(err_msg)
        sys.exit()
    # Check that the zero-lag slide has time_slide_id == 0.
    if not numpy.all(numpy.array(list(time_slide_list[0].values())) == 0):
        err_msg = "The zero-lag slide should have time_slide_id == 0 "
        err_msg += "but the first element of time_slide_list is "
        err_msg += "%s \n" % time_slide_list[0]
        logging.error(err_msg)
        sys.exit()

    return time_slide_list


# =============================================================================
# Function to determine the id of the zero-lag timeslide
# =============================================================================
def find_zero_lag_slide_id(slide_dict):
    """Loads timeslides from PyGRB output file"""

    zero_lag_slide_id = None
    num_slides = len(slide_dict)
    for i in range(num_slides):
        # Is this slide the zero-lag?
        if max(slide_dict[i].values()) == 0:
            if min(slide_dict[i].values()) == 0:
                if zero_lag_slide_id is None:
                    zero_lag_slide_id = i
                else:
                    err_msg = 'zero_lag_slide_id was already assigned: there'
                    err_msg += 'seems to be more than one zero-lag slide!'
                    logging.error(err_msg)
                    sys.exit()

    if zero_lag_slide_id is None:
        err_msg = 'Unable to assign zero_lag_slide_id: '
        err_msg += 'there seems to be no zero-lag slide!'
        logging.error(err_msg)
        sys.exit()

    return zero_lag_slide_id


# =============================================================================
# Function to load the segment dicitonary
# TODO: Can this become local?
# =============================================================================
def load_segment_dict(xml_file):
    """Loads the segment dictionary """

    # Get the mapping table
    # TODO: unclear whether this step is necessary (seems the
    # segment_def_id and time_slide_id are always identical)
    time_slide_map_table = \
        load_xml_table(xml_file, lsctables.TimeSlideSegmentMapTable.tableName)
    segment_map = {
        int(entry.segment_def_id): int(entry.time_slide_id)
        for entry in time_slide_map_table
    }
    # Extract the segment table
    segment_table = load_xml_table(
        xml_file, lsctables.SegmentTable.tableName
        )
    segment_dict = {}
    for entry in segment_table:
        curr_slid_id = segment_map[int(entry.segment_def_id)]
        curr_seg = entry.get()
        if curr_slid_id not in segment_dict.keys():
            segment_dict[curr_slid_id] = segments.segmentlist()
        segment_dict[curr_slid_id].append(curr_seg)
        segment_dict[curr_slid_id].coalesce()

    return segment_dict


# =============================================================================
# Construct the trials from the timeslides, segments, and vetoes
# =============================================================================
def construct_trials(num_slides, seg_dir, seg_dict, ifos, slide_dict, vetoes):
    """Constructs trials from triggers, timeslides, segments and vetoes"""

    trial_dict = {}

    # Get segments
    segs = read_seg_files(seg_dir)

    # Separate segments
    trial_time = abs(segs['on'])

    for slide_id in range(num_slides):
        # These can only *reduce* the analysis time
        curr_seg_list = seg_dict[slide_id]

        # Construct the buffer segment list
        seg_buffer = segments.segmentlist()
        for ifo in ifos:
            slide_offset = slide_dict[slide_id][ifo]
            seg_buffer.append(segments.segment(segs['buffer'][0] -
                                               slide_offset,
                                               segs['buffer'][1] -
                                               slide_offset))
        seg_buffer.coalesce()

        # Construct the ifo list
        slid_vetoes = copy.deepcopy(vetoes)
        for ifo in ifos:
            slid_vetoes[ifo].shift(-slide_dict[slide_id][ifo])

        # Construct trial list and check against buffer
        trial_dict[slide_id] = segments.segmentlist()
        for curr_seg in curr_seg_list:
            iter_int = 0
            while 1:
                trial_end = curr_seg[0] + trial_time*(iter_int+1)
                if trial_end > curr_seg[1]:
                    break
                curr_trial = segments.segment(trial_end - trial_time,
                                              trial_end)
                if not seg_buffer.intersects_segment(curr_trial):
                    for ifo in ifos:
                        if slid_vetoes[ifo].intersects_segment(curr_trial):
                            break
                    else:
                        trial_dict[slide_id].append(curr_trial)
                iter_int += 1

    return trial_dict


# =============================================================================
# Find max and median of loudest SNRs or BestNRs
# =============================================================================
def sort_stat(time_veto_max_stat):
    """Sort a dictionary of loudest SNRs/BestNRs"""

    full_time_veto_max_stat = numpy.concatenate(time_veto_max_stat.values())
    full_time_veto_max_stat.sort()

    return full_time_veto_max_stat


# =============================================================================
# Find max and median of loudest SNRs or BestNRs
# =============================================================================
def max_median_stat(num_slides, time_veto_max_stat, trig_stat, total_trials):
    """Deterine the maximum and median of the loudest SNRs/BestNRs"""

    max_stat = max([trig_stat[slide_id].max() if trig_stat[slide_id].size
                   else 0 for slide_id in range(num_slides)])

    full_time_veto_max_stat = sort_stat(time_veto_max_stat)

    if total_trials % 2:
        median_stat = full_time_veto_max_stat[(total_trials - 1) // 2]
    else:
        median_stat = numpy.mean((full_time_veto_max_stat)
                                 [total_trials//2 - 1: total_trials//2 + 1])

    return max_stat, median_stat, full_time_veto_max_stat


# =============================================================================
# Function to determine calibration and waveform errors for injection sets
# =============================================================================
def mc_cal_wf_errs(num_mc_injs, inj_dists, cal_err, wf_err, max_dc_cal_err):
    """Includes calibration and waveform errors by running an MC"""

    # The efficiency calculations include calibration and waveform
    # errors incorporated by running over each injection num_mc_injs times,
    # where each time we draw a random value of distance.

    num_injs = len(inj_dists)

    inj_dist_mc = numpy.ndarray((num_mc_injs+1, num_injs))
    inj_dist_mc[0, :] = inj_dists
    for i in range(num_mc_injs):
        cal_dist_red = stats.norm.rvs(size=num_injs) * cal_err
        wf_dist_red = numpy.abs(stats.norm.rvs(size=num_injs) * wf_err)
        inj_dist_mc[i+1, :] = inj_dists / (max_dc_cal_err *
                                           (1 + cal_dist_red) *
                                           (1 + wf_dist_red))

    return inj_dist_mc
