# Copyright (C) 2018 Tito Dal Canton
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

import unittest
import os
import shutil
import random
import tempfile
import itertools
import numpy as np
from utils import parse_args_cpu_only, simple_exit
from pycbc.types import TimeSeries, FrequencySeries
from pycbc.io.live import SingleCoincForGraceDB
from pycbc.ligolw import ligolw
from pycbc.ligolw import lsctables
from pycbc.ligolw import table
from pycbc.ligolw import utils as ligolw_utils


parse_args_cpu_only("io.live")

class ContentHandler(ligolw.LIGOLWContentHandler):
    pass
lsctables.use_in(ContentHandler)

class TestIOLive(unittest.TestCase):
    def setUp(self):
        self.template = {'template_id': 0,
                         'mass1': 10,
                         'mass2': 11,
                         'spin1x': 0,
                         'spin1y': 0,
                         'spin1z': 0,
                         'spin2x': 0,
                         'spin2y': 0,
                         'spin2z': 0}

        self.possible_ifos = 'H1 L1 V1 K1 I1'.split()

    def do_test(self, n_ifos, n_ifos_followup):
        all_ifos = random.sample(self.possible_ifos, n_ifos + n_ifos_followup)
        trig_ifos = all_ifos[0:n_ifos]
        fup_ifos = list(set(all_ifos) - set(trig_ifos))

        results = {'foreground/stat': np.random.uniform(4, 20),
                   'foreground/ifar': np.random.uniform(0.01, 1000)}
        followup_data = {}
        for ifo in all_ifos:
            offset = 10000 + np.random.uniform(-0.02, 0.02)
            amplitude = np.random.uniform(4, 20)

            # generate a mock SNR time series with a peak
            n = 201
            dt = 1. / 2048.
            t = np.arange(n) * dt
            t_peak = dt * n / 2
            snr = np.exp(-(t - t_peak) ** 2 * 3e-3 ** -2) * amplitude
            snr_series = TimeSeries((snr + 1j * 0).astype(np.complex64),
                                    delta_t=dt, epoch=offset)

            # generate a mock PSD
            psd_samples = np.random.exponential(size=1024)
            psd = FrequencySeries(psd_samples, delta_f=1.)

            # fill in the various fields
            if ifo in trig_ifos:
                base = 'foreground/' + ifo + '/'
                results[base + 'end_time'] = t_peak + offset
                results[base + 'snr'] = amplitude
                results[base + 'sigmasq'] = np.random.uniform(1e6, 2e6)
            followup_data[ifo] = {'snr_series': snr_series,
                                  'psd': psd}

        for ifo, k in itertools.product(trig_ifos, self.template):
            results['foreground/' + ifo + '/' + k] = self.template[k]

        kwargs = {'gracedb_server': 'localhost',
                  'followup_data': followup_data}
        coinc = SingleCoincForGraceDB(trig_ifos, results, **kwargs)

        tempdir = tempfile.mkdtemp()

        # pretend to upload the event to GraceDB.
        # This will fail, but it should not raise an exception
        # and it should leave a bunch of files around
        coinc_file_name = os.path.join(tempdir, 'coinc.xml')
        coinc.upload(coinc_file_name,
                     {ifo: followup_data[ifo]['psd'] for ifo in all_ifos},
                     20., testing=True)

        # read back and check the coinc document
        read_coinc = ligolw_utils.load_filename(
                coinc_file_name, verbose=False, contenthandler=ContentHandler)
        single_table = table.get_table(
                read_coinc, lsctables.SnglInspiralTable.tableName)
        self.assertEqual(len(all_ifos), len(single_table))

        self.assertTrue(
                os.path.isfile(os.path.join(tempdir, 'coinc-psd.xml.gz')))

        shutil.rmtree(tempdir)

    def test_2_ifos_no_followup(self):
        self.do_test(2, 0)

    def test_3_ifos_no_followup(self):
        self.do_test(3, 0)

    def test_4_ifos_no_followup(self):
        self.do_test(4, 0)

    def test_5_ifos_no_followup(self):
        self.do_test(5, 0)

    def test_2_ifos_1_followup(self):
        self.do_test(2, 1)

    def test_2_ifos_2_followup(self):
        self.do_test(2, 2)


suite = unittest.TestSuite()
suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestIOLive))

if __name__ == '__main__':
    results = unittest.TextTestRunner(verbosity=2).run(suite)
    simple_exit(results)
