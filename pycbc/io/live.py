import logging
import os
import pathlib
import datetime
import pycbc
import h5py
import numpy
import json
import copy
from multiprocessing.dummy import threading

import lal
from lal import gpstime as lalgps
from ligo.lw import ligolw
from ligo.lw import lsctables
from ligo.lw import utils as ligolw_utils

from pycbc import version as pycbc_version
from pycbc import pnutils
from pycbc.io.ligolw import (
    return_empty_sngl,
    create_process_table,
    make_psd_xmldoc,
    snr_series_to_xml
)
from pycbc.results import generate_asd_plot, generate_snr_plot
from pycbc.results import source_color
from pycbc.mchirp_area import calc_probabilities


class CandidateForGraceDB(object):
    """This class provides an interface for uploading candidates to GraceDB.
    """

    def __init__(self, coinc_ifos, ifos, coinc_results, **kwargs):
        """Initialize a representation of a zerolag candidate for upload to
        GraceDB.

        Parameters
        ----------
        coinc_ifos: list of strs
            A list of the originally triggered ifos with SNR above threshold
            for this candidate, before possible significance followups.
        ifos: list of strs
            A list of ifos which may have triggers identified in coinc_results
            for this candidate: ifos potentially contributing to significance
        coinc_results: dict of values
            A dictionary of values. The format is defined in
            `pycbc/events/coinc.py` and matches the on-disk representation in
            the hdf file for this time.
        psds: dict of FrequencySeries
            Dictionary providing PSD estimates for all detectors observing.
        low_frequency_cutoff: float
            Minimum valid frequency for the PSD estimates.
        high_frequency_cutoff: float, optional
            Maximum frequency considered for the PSD estimates. Default None.
        skyloc_data: dict of dicts, optional
            Dictionary providing SNR time series for each detector, to be used
            in sky localization with BAYESTAR. The format should be
            `skyloc_data['H1']['snr_series']`. More detectors can be present
            than in `ifos`; if so, extra detectors will only be used for sky
            localization.
        channel_names: dict of strings, optional
            Strain channel names for each detector. Will be recorded in the
            `sngl_inspiral` table.
        padata: PAstroData instance
            Organizes info relevant to the astrophysical probability of the
            candidate.
        mc_area_args: dict of dicts, optional
            Dictionary providing arguments to be used in source probability
            estimation with `pycbc/mchirp_area.py`.
        """
        self.coinc_results = coinc_results
        self.psds = kwargs['psds']
        self.basename = None
        if kwargs.get('gracedb'):
            self.gracedb = kwargs['gracedb']

        # Determine if the candidate should be marked as HWINJ
        self.is_hardware_injection = ('HWINJ' in coinc_results
                                      and coinc_results['HWINJ'])

        # We may need to apply a time offset for premerger search
        self.time_offset = 0
        rtoff = f'foreground/{ifos[0]}/time_offset'
        if rtoff in coinc_results:
            self.time_offset = coinc_results[rtoff]

        # Check for ifos with SNR peaks in coinc_results
        self.et_ifos = [i for i in ifos if f'foreground/{i}/end_time' in
                        coinc_results]

        if 'skyloc_data' in kwargs:
            sld = kwargs['skyloc_data']
            assert len({sld[ifo]['snr_series'].delta_t for ifo in sld}) == 1, \
                    "delta_t for all ifos do not match"
            snr_ifos = sld.keys()  # Ifos with SNR time series calculated
            self.snr_series = {ifo: sld[ifo]['snr_series'] for ifo in snr_ifos}
            # Extra ifos have SNR time series but not sngl inspiral triggers

            for ifo in snr_ifos:
                # Ifos used for sky loc must have a PSD
                assert ifo in self.psds
                self.snr_series[ifo].start_time += self.time_offset
        else:
            self.snr_series = None
            snr_ifos = self.et_ifos

        # Set up the bare structure of the xml document
        outdoc = ligolw.Document()
        outdoc.appendChild(ligolw.LIGO_LW())

        proc_id = create_process_table(outdoc, program_name='pycbc',
                                       detectors=snr_ifos).process_id

        # Set up coinc_definer table
        coinc_def_table = lsctables.New(lsctables.CoincDefTable)
        coinc_def_id = lsctables.CoincDefID(0)
        coinc_def_row = lsctables.CoincDef()
        coinc_def_row.search = "inspiral"
        coinc_def_row.description = "sngl_inspiral<-->sngl_inspiral coincs"
        coinc_def_row.coinc_def_id = coinc_def_id
        coinc_def_row.search_coinc_type = 0
        coinc_def_table.append(coinc_def_row)
        outdoc.childNodes[0].appendChild(coinc_def_table)

        # Set up coinc inspiral and coinc event tables
        coinc_id = lsctables.CoincID(0)
        coinc_event_table = lsctables.New(lsctables.CoincTable)
        coinc_event_row = lsctables.Coinc()
        coinc_event_row.coinc_def_id = coinc_def_id
        coinc_event_row.nevents = len(snr_ifos)
        coinc_event_row.instruments = ','.join(snr_ifos)
        coinc_event_row.time_slide_id = lsctables.TimeSlideID(0)
        coinc_event_row.process_id = proc_id
        coinc_event_row.coinc_event_id = coinc_id
        coinc_event_row.likelihood = 0.
        coinc_event_table.append(coinc_event_row)
        outdoc.childNodes[0].appendChild(coinc_event_table)

        # Set up sngls
        sngl_inspiral_table = lsctables.New(lsctables.SnglInspiralTable)
        coinc_event_map_table = lsctables.New(lsctables.CoincMapTable)

        # Marker variable recording template info from a valid sngl trigger
        sngl_populated = None
        network_snrsq = 0
        for sngl_id, ifo in enumerate(snr_ifos):
            sngl = return_empty_sngl(nones=True)
            sngl.event_id = lsctables.SnglInspiralID(sngl_id)
            sngl.process_id = proc_id
            sngl.ifo = ifo
            names = [n.split('/')[-1] for n in coinc_results
                     if f'foreground/{ifo}' in n]
            for name in names:
                val = coinc_results[f'foreground/{ifo}/{name}']
                if name == 'end_time':
                    val += self.time_offset
                    sngl.end = lal.LIGOTimeGPS(val)
                else:
                    # Sngl inspirals have a restricted set of attributes
                    try:
                        setattr(sngl, name, val)
                    except AttributeError:
                        pass
            if sngl.mass1 and sngl.mass2:
                sngl.mtotal, sngl.eta = pnutils.mass1_mass2_to_mtotal_eta(
                        sngl.mass1, sngl.mass2)
                sngl.mchirp, _ = pnutils.mass1_mass2_to_mchirp_eta(
                        sngl.mass1, sngl.mass2)
                sngl_populated = sngl
            if sngl.snr:
                sngl.eff_distance = sngl.sigmasq ** 0.5 / sngl.snr
                network_snrsq += sngl.snr ** 2.0
            if 'channel_names' in kwargs and ifo in kwargs['channel_names']:
                sngl.channel = kwargs['channel_names'][ifo]
            sngl_inspiral_table.append(sngl)

            # Set up coinc_map entry
            coinc_map_row = lsctables.CoincMap()
            coinc_map_row.table_name = 'sngl_inspiral'
            coinc_map_row.coinc_event_id = coinc_id
            coinc_map_row.event_id = sngl.event_id
            coinc_event_map_table.append(coinc_map_row)

            if self.snr_series is not None:
                snr_series_to_xml(self.snr_series[ifo], outdoc, sngl.event_id)

        # Set merger time to the mean of trigger peaks over coinc_results ifos
        self.merger_time = \
            numpy.mean([coinc_results[f'foreground/{ifo}/end_time'] for ifo in
                        self.et_ifos]) \
            + self.time_offset

        outdoc.childNodes[0].appendChild(coinc_event_map_table)
        outdoc.childNodes[0].appendChild(sngl_inspiral_table)

        # Set up the coinc inspiral table
        coinc_inspiral_table = lsctables.New(lsctables.CoincInspiralTable)
        coinc_inspiral_row = lsctables.CoincInspiral()
        # This seems to be used as FAP, which should not be in gracedb
        coinc_inspiral_row.false_alarm_rate = 0.
        coinc_inspiral_row.minimum_duration = 0.
        coinc_inspiral_row.instruments = tuple(snr_ifos)
        coinc_inspiral_row.coinc_event_id = coinc_id
        coinc_inspiral_row.mchirp = sngl_populated.mchirp
        coinc_inspiral_row.mass = sngl_populated.mtotal
        coinc_inspiral_row.end_time = sngl_populated.end_time
        coinc_inspiral_row.end_time_ns = sngl_populated.end_time_ns
        coinc_inspiral_row.snr = network_snrsq ** 0.5
        far = 1.0 / (lal.YRJUL_SI * coinc_results['foreground/ifar'])
        coinc_inspiral_row.combined_far = far
        coinc_inspiral_table.append(coinc_inspiral_row)
        outdoc.childNodes[0].appendChild(coinc_inspiral_table)

        # Append the PSDs
        psds_lal = {}
        for ifo, psd in self.psds.items():
            kmin = int(kwargs['low_frequency_cutoff'] / psd.delta_f)
            fseries = lal.CreateREAL8FrequencySeries(
                "psd", psd.epoch, kwargs['low_frequency_cutoff'], psd.delta_f,
                lal.StrainUnit**2 / lal.HertzUnit, len(psd) - kmin)
            fseries.data.data = psd.numpy()[kmin:] / pycbc.DYN_RANGE_FAC ** 2.0
            psds_lal[ifo] = fseries
        make_psd_xmldoc(psds_lal, outdoc)

        # P astro calculation
        if 'padata' in kwargs:
            if 'p_terr' in kwargs:
                raise RuntimeError("Both p_astro calculation data and a "
                    "previously calculated p_terr value were provided, this "
                    "doesn't make sense!")
            assert len(coinc_ifos) < 3, \
                f"p_astro can't handle {coinc_ifos} coinc ifos!"
            trigger_data = {
                'mass1': sngl_populated.mass1,
                'mass2': sngl_populated.mass2,
                'spin1z': sngl_populated.spin1z,
                'spin2z': sngl_populated.spin2z,
                'network_snr': network_snrsq ** 0.5,
                'far': far,
                'triggered': coinc_ifos,
                # Consider all ifos potentially relevant to detection,
                # ignore those that only contribute to sky loc
                'sensitive': self.et_ifos}
            horizons = {i: self.psds[i].dist for i in self.et_ifos}
            self.p_astro, self.p_terr = \
                kwargs['padata'].do_pastro_calc(trigger_data, horizons)
        elif 'p_terr' in kwargs:
            self.p_astro, self.p_terr = 1 - kwargs['p_terr'], kwargs['p_terr']
        else:
            self.p_astro, self.p_terr = None, None

        # Source probabilities and hasmassgap estimation
        self.probabilities = None
        self.hasmassgap = None
        if 'mc_area_args' in kwargs:
            eff_distances = [sngl.eff_distance for sngl in sngl_inspiral_table]
            self.probabilities = calc_probabilities(coinc_inspiral_row.mchirp,
                                                    coinc_inspiral_row.snr,
                                                    min(eff_distances),
                                                    kwargs['mc_area_args'])
            if 'embright_mg_max' in kwargs['mc_area_args']:
                hasmg_args = copy.deepcopy(kwargs['mc_area_args'])
                hasmg_args['mass_gap'] = True
                hasmg_args['mass_bdary']['gap_max'] = \
                    kwargs['mc_area_args']['embright_mg_max']
                self.hasmassgap = calc_probabilities(
                                      coinc_inspiral_row.mchirp,
                                      coinc_inspiral_row.snr,
                                      min(eff_distances),
                                      hasmg_args)['Mass Gap']

        # Combine p astro and source probs
        if self.p_astro is not None and self.probabilities is not None:
            self.astro_probs = {cl: pr * self.p_astro for
                                cl, pr in self.probabilities.items()}
            self.astro_probs['Terrestrial'] = self.p_terr
        else:
            self.astro_probs = None

        self.outdoc = outdoc
        self.time = sngl_populated.end

    def save(self, fname):
        """Write a file representing this candidate in a LIGOLW XML format
        compatible with GraceDB.

        Parameters
        ----------
        fname: str
            Name of file to write to disk.
        """
        kwargs = {}
        if threading.current_thread() is not threading.main_thread():
            # avoid an error due to no ability to do signal handling in threads
            kwargs['trap_signals'] = None
        ligolw_utils.write_filename(self.outdoc, fname, \
            compress='auto', **kwargs)

        save_dir = os.path.dirname(fname)
        # Save EMBright properties info as json
        if self.hasmassgap is not None:
            self.embright_file = os.path.join(save_dir, 'pycbc.em_bright.json')
            with open(self.embright_file, 'w') as embrightf:
                json.dump({'HasMassGap': self.hasmassgap}, embrightf)
            logging.info('EM Bright file saved as %s', self.embright_file)

        # Save multi-cpt p astro as json
        if self.astro_probs is not None:
            self.multipa_file = os.path.join(save_dir, 'pycbc.p_astro.json')
            with open(self.multipa_file, 'w') as multipaf:
                json.dump(self.astro_probs, multipaf)
            logging.info('Multi p_astro file saved as %s', self.multipa_file)

        # Save source probabilities in a json file
        if self.probabilities is not None:
            self.prob_file = os.path.join(save_dir, 'src_probs.json')
            with open(self.prob_file, 'w') as probf:
                json.dump(self.probabilities, probf)
            logging.info('Source probabilities file saved as %s', self.prob_file)
            # Don't save any other files!
            return

        # Save p astro / p terr as json
        if self.p_astro is not None:
            self.pastro_file = os.path.join(save_dir, 'pa_pterr.json')
            with open(self.pastro_file, 'w') as pastrof:
                json.dump({'p_astro': self.p_astro, 'p_terr': self.p_terr},
                          pastrof)
            logging.info('P_astro file saved as %s', self.pastro_file)

    def upload(self, fname, gracedb_server=None, testing=True,
               extra_strings=None, search='AllSky', labels=None):
        """Upload this candidate to GraceDB, and annotate it with a few useful
        plots and comments.

        Parameters
        ----------
        fname: str
            The name to give the xml file associated with this trigger
        gracedb_server: string, optional
            URL to the GraceDB web API service for uploading the event.
            If omitted, the default will be used.
        testing: bool
            Switch to determine if the upload should be sent to gracedb as a
            test trigger (True) or a production trigger (False).
        search: str
            String going into the "search" field of the GraceDB event.
        labels: list
            Optional list of labels to tag the new event with.
        """
        import pylab as pl

        if fname.endswith('.xml.gz'):
            self.basename = fname.replace('.xml.gz', '')
        elif fname.endswith('.xml'):
            self.basename = fname.replace('.xml', '')
        else:
            raise ValueError("Upload filename must end in .xml or .xml.gz, got"
                             " %s" % fname)

        # First make sure the event is saved on disk
        # as GraceDB operations can fail later
        self.save(fname)

        # hardware injections need to be maked with the INJ tag
        if self.is_hardware_injection:
            labels = (labels or []) + ['INJ']

        # connect to GraceDB if we are not reusing a connection
        if not hasattr(self, 'gracedb'):
            logging.info('Connecting to GraceDB')
            gdbargs = {'reload_certificate': True, 'reload_buffer': 300}
            if gracedb_server:
                gdbargs['service_url'] = gracedb_server
            try:
                from ligo.gracedb.rest import GraceDb
                self.gracedb = GraceDb(**gdbargs)
            except Exception as exc:
                logging.error('Failed to create GraceDB client')
                logging.error(exc)

        # create GraceDB event
        logging.info('Uploading %s to GraceDB', fname)
        group = 'Test' if testing else 'CBC'
        gid = None
        try:
            response = self.gracedb.create_event(
                group,
                "pycbc",
                fname,
                search=search,
                labels=labels
            )
            gid = response.json()["graceid"]
            logging.info("Uploaded event %s", gid)
        except Exception as exc:
            logging.error('Failed to create GraceDB event')
            logging.error(str(exc))

        # Upload em_bright properties JSON
        if self.hasmassgap is not None and gid is not None:
            try:
                self.gracedb.write_log(
                    gid, 'EM Bright properties JSON file upload',
                    filename=self.embright_file,
                    tag_name=['em_bright']
                )
                logging.info('Uploaded em_bright properties for %s', gid)
            except Exception as exc:
                logging.error('Failed to upload em_bright properties file '
                              'for %s', gid)
                logging.error(str(exc))

        # Upload multi-cpt p_astro JSON
        if self.astro_probs is not None and gid is not None:
            try:
                self.gracedb.write_log(
                    gid, 'Multi-component p_astro JSON file upload',
                    filename=self.multipa_file,
                    tag_name=['p_astro'],
                    label='PASTRO_READY'
                )
                logging.info('Uploaded multi p_astro for %s', gid)
            except Exception as exc:
                logging.error(
                    'Failed to upload multi p_astro file for %s',
                    gid
                )
                logging.error(str(exc))

        # If there is p_astro but no probabilities, upload p_astro JSON
        if hasattr(self, 'pastro_file') and gid is not None:
            try:
                self.gracedb.write_log(
                    gid, '2-component p_astro JSON file upload',
                    filename=self.pastro_file,
                    tag_name=['sig_info']
                )
                logging.info('Uploaded p_astro for %s', gid)
            except Exception as exc:
                logging.error('Failed to upload p_astro file for %s', gid)
                logging.error(str(exc))

        # plot the SNR timeseries and noise PSDs
        if self.snr_series is not None:
            snr_series_fname = self.basename + '.hdf'
            snr_series_plot_fname = self.basename + '_snr.png'
            asd_series_plot_fname = self.basename + '_asd.png'

            triggers = {
                ifo: (self.coinc_results[f'foreground/{ifo}/end_time']
                      + self.time_offset,
                      self.coinc_results[f'foreground/{ifo}/snr'])
                for ifo in self.et_ifos
                }
            ref_time = int(self.merger_time)
            generate_snr_plot(self.snr_series, snr_series_plot_fname,
                              triggers, ref_time)

            generate_asd_plot(self.psds, asd_series_plot_fname)

            for ifo in sorted(self.snr_series):
                curr_snrs = self.snr_series[ifo]
                curr_snrs.save(snr_series_fname, group='%s/snr' % ifo)

            # Additionally save the PSDs into the snr_series file
            for ifo in sorted(self.psds):
                # Undo dynamic range factor
                curr_psd = self.psds[ifo].astype(numpy.float64)
                curr_psd /= pycbc.DYN_RANGE_FAC ** 2.0
                curr_psd.save(snr_series_fname, group='%s/psd' % ifo)

        # Upload SNR series in HDF format and plots
        if self.snr_series is not None and gid is not None:
            try:
                self.gracedb.write_log(
                    gid, 'SNR timeseries HDF file upload',
                    filename=snr_series_fname
                )
                self.gracedb.write_log(
                    gid, 'SNR timeseries plot upload',
                    filename=snr_series_plot_fname,
                    tag_name=['background'],
                    displayName=['SNR timeseries']
                )
                self.gracedb.write_log(
                    gid, 'ASD plot upload',
                    filename=asd_series_plot_fname,
                    tag_name=['psd'], displayName=['ASDs']
                )
            except Exception as exc:
                logging.error('Failed to upload SNR timeseries and ASD for %s',
                              gid)
                logging.error(str(exc))

        # If 'self.prob_file' exists, make pie plot and do uploads.
        # The pie plot only shows relative astrophysical source
        # probabilities, not p_astro vs p_terrestrial
        if hasattr(self, 'prob_file'):
            self.prob_plotf = self.prob_file.replace('.json', '.png')
            # Don't try to plot zero probabilities
            prob_plot = {k: v for (k, v) in self.probabilities.items()
                         if v != 0.0}
            labels, sizes = zip(*prob_plot.items())
            colors = [source_color(label) for label in labels]
            fig, ax = pl.subplots()
            ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                   textprops={'fontsize': 15})
            ax.axis('equal')
            fig.savefig(self.prob_plotf)
            pl.close()
            if gid is not None:
                try:
                    self.gracedb.write_log(
                        gid,
                        'Source probabilities JSON file upload',
                        filename=self.prob_file,
                        tag_name=['pe']
                    )
                    logging.info('Uploaded source probabilities for %s', gid)
                    self.gracedb.write_log(
                        gid,
                        'Source probabilities plot upload',
                        filename=self.prob_plotf,
                        tag_name=['pe']
                    )
                    logging.info(
                        'Uploaded source probabilities pie chart for %s',
                        gid
                    )
                except Exception as exc:
                    logging.error(
                        'Failed to upload source probability results for %s',
                        gid
                    )
                    logging.error(str(exc))

        if gid is not None:
            try:
                # Add code version info
                gracedb_tag_with_version(self.gracedb, gid)
                # Add any annotations to the event log
                for text in (extra_strings or []):
                    self.gracedb.write_log(
                        gid, text, tag_name=['analyst_comments'])
            except Exception as exc:
                logging.error('Something failed during annotation of analyst'
                              ' comments for event %s on GraceDB.', fname)
                logging.error(str(exc))

        return gid


def gracedb_tag_with_version(gracedb, event_id):
    """Add a GraceDB log entry reporting PyCBC's version and install location.
    """
    version_str = 'Using PyCBC version {}{} at {}'
    version_str = version_str.format(
            pycbc_version.version,
            ' (release)' if pycbc_version.release else '',
            os.path.dirname(pycbc.__file__))
    gracedb.write_log(event_id, version_str)


def maximum_string(numbers):
    """
    Find the maximum possible length string to match
    all values between two numbers

    Parameters
    ----------
    numbers : list of integers
        the numbers to find the string which will match all of them
    """
    # The max length of the number will be the integer above log10
    # of the biggest number
    maxlen = int(numpy.ceil(numpy.log10(max(numbers))))
    # Convert the numbers to (possibly leading zero-padded) strings
    strings = [f"{{n:0{maxlen:d}d}}".format(n=n) for n in numbers]
    # Count how many digits are the same:
    n_digits = 0
    for str_digit in zip(*strings):
        if len(numpy.unique(str_digit)) == 1:
            # This digit is the same for all numbers
            n_digits += 1
        else:
            break
    return strings[0][:n_digits]


def filter_file(filename, start_time, end_time):
    """
    Does filename indicate that any of the file is within the
    start and end times?
    Parameters
    ----------
    filename : string
        Filename which matches the format
        {id_string}-{start_time}-{duration}.hdf
    start_time : float
        Start of search window, i.e. GPS time of when the
        file cannot end before
    end_time : float
        End of search window, i.e. GPS time of when the
        file cannot start after

    Returns
    -------
    boolean
        Does any of the file lie within the start/end times
    """
    # FIX ME eventually - this uses the gps time and duration from the filename
    # Is there a better way? (i.e. trigger gps times in the file or
    # add an attribute)
    fend = filename.split('-')[-2:]
    file_start = float(fend[0])
    duration = float(fend[1][:-4])

    return ((file_start + duration) >= start_time) and (file_start <= end_time)


def add_live_trigger_selection_options(parser):
    """
    Add options required for obtaining the right set of PyCBC live triggers
    into an argument parser
    """
    finding_group = parser.add_argument_group('Trigger Finding')
    finding_group.add_argument(
        "--trigger-directory",
        metavar="PATH",
        required=True,
        help="Directory containing trigger files, directory "
             "can contain subdirectories. Required."
    )
    finding_group.add_argument(
        "--gps-start-time",
        type=int,
        required=True,
        help="Start time of the analysis. Integer, required"
    )
    finding_group.add_argument(
        "--gps-end-time",
        type=int,
        required=True,
        help="End time of the analysis. Integer, required"
    )
    finding_group.add_argument(
        "--date-directories",
        action="store_true",
        help="Are the triggers stored in directories according "
             "to the date?"
    )
    default_dd_format = "%Y_%m_%d"
    finding_group.add_argument(
        "--date-directory-format",
        default=default_dd_format,
        help="Format of date, see datetime strftime "
             "documentation for details. Default: "
             "%%Y_%%m_%%d"
    )
    finding_group.add_argument(
        "--file-identifier",
        default="H1L1V1-Live",
        help="String required in filename to be considered for "
             "analysis. Default: 'H1L1V1-Live'."
    )


def add_live_significance_trigger_pruning_options(parser):
    """
    Add options used for pruning in live singles significance fits
    """
    pruning_group = parser.add_argument_group("Trigger pruning")
    pruning_group.add_argument(
        "--prune-loudest",
        type=int,
        help="Maximum number of loudest trigger clusters to "
             "remove from each bin."
    )
    pruning_group.add_argument(
        "--prune-window",
        type=float,
        help="Window (seconds) either side of the --prune-loudest "
             "loudest triggers in each duration bin to remove."
    )
    pruning_group.add_argument(
        "--prune-stat-threshold",
        type=float,
        help="Minimum statistic value to consider a "
             "trigger for pruning."
    )


def verify_live_significance_trigger_pruning_options(args, parser):
    """
    Verify options used for pruning in live singles significance fits
    """
    # Pruning options are mutually required or not needed
    prune_options = [args.prune_loudest, args.prune_window,
                     args.prune_stat_threshold]

    if any(prune_options) and not all(prune_options):
        parser.error("Require all or none of --prune-loudest, "
                     "--prune-window and --prune-stat-threshold")


def add_live_significance_duration_bin_options(parser):
    """
    Add options used to calculate duration bin edges in live
    singles significance fits
    """
    durbin_group = parser.add_argument_group('Duration Bins')
    durbin_group.add_argument(
        "--duration-bin-edges",
        nargs='+',
        type=float,
        help="Durations to use for bin edges. "
             "Use if specifying exact bin edges, "
             "Not compatible with --duration-bin-start, "
             "--duration-bin-end and --num-duration-bins"
    )
    durbin_group.add_argument(
        "--duration-bin-start",
        type=float,
        help="Shortest duration to use for duration bins."
             "Not compatible with --duration-bins, requires "
             "--duration-bin-end and --num-duration-bins."
    )
    durbin_group.add_argument(
        "--duration-bin-end", type=float,
        help="Longest duration to use for duration bins."
    )
    durbin_group.add_argument(
        "--duration-from-bank",
        help="Path to the template bank file to get max/min "
             "durations from."
    )
    durbin_group.add_argument(
        "--num-duration-bins",
        type=int,
        help="How many template duration bins to split the bank "
             "into before fitting."
    )
    durbin_group.add_argument(
        "--duration-bin-spacing",
        choices=['linear', 'log'],
        default='log',
        help="How to set spacing for bank split "
             "if using --num-duration-bins and "
             "--duration-bin-start + --duration-bin-end "
             "or --duration-from-bank."
    )


def verify_live_significance_duration_bin_options(args, parser):
    """
    Verify options used to calculate duration bin edges in live
    singles significance fits
    """
    # Check the bin options
    if args.duration_bin_edges:
        if (args.duration_bin_start or args.duration_bin_end or
                args.duration_from_bank or args.num_duration_bins):
            parser.error("Cannot use --duration-bin-edges with "
                         "--duration-bin-start, --duration-bin-end, "
                         "--duration-from-bank or --num-duration-bins.")
    else:
        if not args.num_duration_bins:
            parser.error("--num-duration-bins must be set if not using "
                         "--duration-bin-edges.")
        if not ((args.duration_bin_start and args.duration_bin_end) or
                args.duration_from_bank):
            parser.error("--duration-bin-start & --duration-bin-end or "
                         "--duration-from-bank must be set if not using "
                         "--duration-bin-edges.")
    if args.duration_bin_end and \
            args.duration_bin_end <= args.duration_bin_start:
        parser.error("--duration-bin-end must be greater than "
                     "--duration-bin-start, got "
                     f"{args.duration_bin_end} and {args.duration_bin_start}")


def find_trigger_files(directory, gps_start_time, gps_end_time,
                       id_string='*', date_directories=False,
                       date_directory_format="%Y_%m_%d"):
    """
    Find a list of PyCBC live trigger files which are between the gps
    start and end times given
    """

    # Find the string at the start of the gps time which will match all
    # files in this range - this helps to cut which ones we need to
    # compare later
    num_match = maximum_string([gps_start_time, gps_end_time])

    # ** means recursive, so for large directories, this is expensive.
    # It is not too bad if date_directories is set, as we don't waste time
    # in directories where there cant be any files.
    glob_string = f'**/*{id_string}*{num_match}*.hdf'
    if date_directories:
        # convert the GPS times into dates, and only use the directories
        # of those dates to search
        # Add a day on either side to ensure we get files which straddle
        # the boundary
        one_day = datetime.timedelta(days=1)
        date_check = lalgps.gps_to_utc(gps_start_time) - one_day
        date_end = lalgps.gps_to_utc(gps_end_time) + one_day
        matching_files = []
        while date_check < date_end:
            date_dir = date_check.strftime(date_directory_format)
            subdir = os.path.join(directory, date_dir)
            matching_files_gen = pathlib.Path(subdir).glob(glob_string)
            matching_files += [f.as_posix() for f in matching_files_gen]
            date_check += one_day
    else:
        # Grab all hdf files in the directory
        matching_files_gen = pathlib.Path(directory).glob(glob_string)
        matching_files = [f.as_posix() for f in matching_files_gen]

    # Is the file in the time window?
    matching_files = [f for f in matching_files
                      if filter_file(f, gps_start_time, gps_end_time)]

    return sorted(matching_files)


def find_trigger_files_from_cli(args):
    """
    Wrapper around the find_trigger_files function to use when called using
    options from the add_live_trigger_selection_options function
    """
    return find_trigger_files(
        args.trigger_directory,
        args.gps_start_time,
        args.gps_end_time,
        id_string=args.file_identifier,
        date_directories=args.date_directories,
        date_directory_format=args.date_directory_format
    )


def duration_bins_from_cli(args):
    """Create the duration bins from CLI options.
    """
    if args.duration_bin_edges:
        # direct bin specification
        return numpy.array(args.duration_bin_edges)
    # calculate bins from min/max and number
    min_dur = args.duration_bin_start
    max_dur = args.duration_bin_end
    if args.duration_from_bank:
        # read min/max duration directly from the bank itself
        with h5py.File(args.duration_from_bank, 'r') as bank_file:
            temp_durs = bank_file['template_duration'][:]
        min_dur, max_dur = min(temp_durs), max(temp_durs)
    if args.duration_bin_spacing == 'log':
        return numpy.logspace(
            numpy.log10(min_dur),
            numpy.log10(max_dur),
            args.num_duration_bins + 1
        )
    if args.duration_bin_spacing == 'linear':
        return numpy.linspace(
            min_dur,
            max_dur,
            args.num_duration_bins + 1
        )
    raise RuntimeError("Invalid duration bin specification")


__all__ = [
    'CandidateForGraceDB', 'gracedb_tag_with_version',
    'gracedb_tag_with_version', 'add_live_trigger_selection_options',
    'add_live_significance_trigger_pruning_options',
    'verify_live_significance_trigger_pruning_options',
    'add_live_significance_duration_bin_options',
    'verify_live_significance_duration_bin_options',
    'find_trigger_files', 'find_trigger_files_from_cli',
    'duration_bins_from_cli',
]
