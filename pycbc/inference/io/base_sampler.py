# Copyright (C) 2019 Collin Capano
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# self.option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Provides abstract base class for all samplers."""

from __future__ import absolute_import

import time
from abc import (ABCMeta, abstractmethod)

from six import add_metaclass

from .base_hdf import BaseInferenceFile


@add_metaclass(ABCMeta)
class BaseSamplerFile(BaseInferenceFile):
    """Base HDF class for all samplers.

    This adds abstract methods ``write_resume_point`` and
    ``write_sampler_metadata`` to :py:class:`BaseInferenceFile`.
    """
    def write_run_start_time(self):
        """Writes the current (UNIX) time to the file.

        Times are stored as a list in the file's ``attrs``, with name
        ``run_start_time``. If the attrbute already exists, the current time
        is appended. Otherwise, the attribute will be created and time added.
        """
        attrname = "run_start_time"
        try:
            times = self.attrs[attrname].tolist()
        except KeyError:
            times = []
        times.append(time.time())
        self.attrs[attrname] = times

    @abstractmethod
    def write_resume_point(self):
        """Should write the point that a sampler starts up.

        How the resume point is indexed is up to the sampler. For example,
        MCMC samplers use the number of iterations that are stored in the
        checkpoint file.
        """
        pass

    @abstractmethod
    def write_sampler_metadata(self, sampler):
        """This should write the given sampler's metadata to the file.

        This should also include the model's metadata.
        """
        pass

    def validate(self):
        """Runs a validation test.

        This checks that a samples group exist, and that there are more than
        one sample stored to it.

        Returns
        -------
        bool :
            Whether or not the file is valid as a checkpoint file.
        """
        try:
            group = '{}/{}'.format(self.samples_group, self.variable_params[0])
            checkpoint_valid = self[group].size != 0
        except KeyError:
            checkpoint_valid = False
        return checkpoint_valid
