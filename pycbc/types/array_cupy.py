# Copyright (C) 2012  Alex Nitz
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
"""Numpy based CPU backend for PyCBC Array
"""
import cupy as _xp
from pycbc.types.array import common_kind, complex128, float64
from scipy.linalg import blas
from pycbc.types import real_same_precision_as

def zeros(length, dtype=_xp.float64):
    return _xp.zeros(length, dtype=dtype)

def empty(length, dtype=_xp.float64):
    return _xp.empty(length, dtype=dtype)

def ptr(self):
    return self.data.data.mem.ptr

def dot(self, other):
    return _xp.dot(self._data,other)

def min(self):
    return self.data.min()

def abs_max_loc(self):
    if self.kind == 'real':
        tmp = abs(self.data)
        ind = _xp.argmax(tmp)
        return tmp[ind], ind
    else:
        tmp = self.data.real ** 2.0
        tmp += self.data.imag ** 2.0
        ind = _xp.argmax(tmp)
        return tmp[ind] ** 0.5, ind

def cumsum(self):
    return self.data.cumsum()

def max(self):
    return self.data.max()

def max_loc(self):
    ind = _xp.argmax(self.data)
    return self.data[ind], ind

def take(self, indices):
    return self.data.take(indices)

def weighted_inner(self, other, weight):
    """ Return the inner product of the array with complex conjugation.
    """
    if weight is None:
        return self.inner(other)

    cdtype = common_kind(self.dtype, other.dtype)
    if cdtype.kind == 'c':
        acum_dtype = complex128
    else:
        acum_dtype = float64

    return _xp.sum(self.data.conj() * other / weight, dtype=acum_dtype)

def abs_arg_max(self):
    if self.dtype == _xp.float32 or self.dtype == _xp.float64:
        return _xp.argmax(abs(self.data))
    else:
        return abs_arg_max_complex(self._data)

def inner(self, other):
    """ Return the inner product of the array with complex conjugation.
    """
    cdtype = common_kind(self.dtype, other.dtype)
    if cdtype.kind == 'c':
        return _xp.sum(self.data.conj() * other, dtype=complex128)
    else:
        return inner_real(self.data, other)

def vdot(self, other):
    """ Return the inner product of the array with complex conjugation.
    """
    return _xp.vdot(self.data, other)

def squared_norm(self):
    """ Return the elementwise squared norm of the array """
    return (self.data.real**2 + self.data.imag**2)

#def numpy(self):
#    return self._data

def _copy(self, self_ref, other_ref):
    self_ref[:] = other_ref[:]

def _getvalue(self, index):
    return self._data[index]

def sum(self):
    if self.kind == 'real':
        return _xp.sum(self._data,dtype=float64)
    else:
        return _xp.sum(self._data,dtype=complex128)

def clear(self):
    self[:] = 0

def _scheme_matches_base_array(array):
    if isinstance(array, _xp.ndarray):
        return True
    else:
        return False

def _to_device(array):
    return _xp.asarray(array)

def numpy(self):
    return _xp.asnumpy(self._data)

def _copy_base_array(array):
    return array.copy()

