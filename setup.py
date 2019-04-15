#!/usr/bin/env python
# Copyright (C) 2012 Alex Nitz, Duncan Brown, Andrew Miller, Josh Willis
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
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

"""
setup.py file for PyCBC package
"""

from __future__ import print_function

import os, subprocess, shutil

from distutils.errors import DistutilsError
from distutils.command.clean import clean as _clean

from setuptools.command.install import install as _install
from setuptools import Extension, setup, Command
from setuptools.command.build_ext import build_ext as _build_ext
from setuptools import find_packages

requires = []
setup_requires = ['numpy>=1.13.0,<1.15.3',]
install_requires =  setup_requires + ['Mako>=1.0.1',
                      'cython',
                      'decorator>=3.4.2',
                      'scipy>=0.16.0',
                      'matplotlib>=1.5.1',
                      'pillow',
                      'h5py>=2.5',
                      'jinja2',
                      'astropy>=2.0.3,<3.0.0; python_version <= "2.7"',
                      'astropy>=2.0.3; python_version > "3.4"',
                      'mpld3>=0.3',
                      'lscsoft-glue>=1.59.3',
                      'emcee==2.2.1',
                      'requests>=1.2.1',
                      'beautifulsoup4>=4.6.0',
                      'six>=1.10.0',
                      'ligo-segments',
                      'weave>=0.16.0; python_version <= "2.7"',
                      ]

def find_files(dirname, relpath=None):
    def find_paths(dirname):
        items = []
        for fname in os.listdir(dirname):
            path = os.path.join(dirname, fname)
            if os.path.isdir(path):
                items += find_paths(path)
            elif not path.endswith(".py") and not path.endswith(".pyc"):
                items.append(path)
        return items
    items = find_paths(dirname)
    if relpath is None:
        relpath = dirname
    return [os.path.relpath(path, relpath) for path in items]

class cbuild_ext(_build_ext):
    def run(self):
        import pkg_resources

        # At this point we can be sure pip has already installed numpy
        numpy_incl = pkg_resources.resource_filename('numpy', 'core/include')

        for ext in self.extensions:
            if (hasattr(ext, 'include_dirs') and
                    numpy_incl not in ext.include_dirs):
                ext.include_dirs.append(numpy_incl)

        _build_ext.run(self)


# Add swig-generated files to the list of things to clean, so they
# get regenerated each time.
class clean(_clean):
    def finalize_options (self):
        _clean.finalize_options(self)
        self.clean_files = []
        self.clean_folders = ['docs/_build']
    def run(self):
        _clean.run(self)
        for f in self.clean_files:
            try:
                os.unlink(f)
                print('removed {0}'.format(f))
            except:
                pass

        for fol in self.clean_folders:
            shutil.rmtree(fol, ignore_errors=True)
            print('removed {0}'.format(fol))

# write versioning info
def get_version_info():
    """Get VCS info and write version info to version.py
    """
    from pycbc import _version_helper

    class vdummy(object):
        def __getattr__(self, attr):
            return ''

    # If this is a pycbc git repo always populate version information using GIT
    try:
        vinfo = _version_helper.generate_git_version_info()
    except:
        vinfo = vdummy()
        vinfo.version = '1.13.dev9'
        vinfo.release = 'False'

    with open('pycbc/version.py', 'w') as f:
        f.write("# coding: utf-8\n")
        f.write("# Generated by setup.py for PyCBC on %s.\n\n"
                % vinfo.build_date)

        # print general info
        f.write('version = \'%s\'\n' % vinfo.version)
        f.write('date = \'%s\'\n' % vinfo.date)
        f.write('release = %s\n' % vinfo.release)
        f.write('last_release = \'%s\'\n' % vinfo.last_release)

        # print git info
        f.write('\ngit_hash = \'%s\'\n' % vinfo.hash)
        f.write('git_branch = \'%s\'\n' % vinfo.branch)
        f.write('git_tag = \'%s\'\n' % vinfo.tag)
        f.write('git_author = \'%s\'\n' % vinfo.author)
        f.write('git_committer = \'%s\'\n' % vinfo.committer)
        f.write('git_status = \'%s\'\n' % vinfo.status)
        f.write('git_builder = \'%s\'\n' % vinfo.builder)
        f.write('git_build_date = \'%s\'\n' % vinfo.build_date)
        f.write('git_verbose_msg = """Version: %s\n'
                'Branch: %s\n'
                'Tag: %s\n'
                'Id: %s\n'
                'Builder: %s\n'
                'Build date: %s\n'
                'Repository status is %s"""\n' %(
                                               vinfo.version,
                                               vinfo.branch,
                                               vinfo.tag,
                                               vinfo.hash,
                                               vinfo.builder,
                                               vinfo.build_date,
                                               vinfo.status))
        f.write('from pycbc._version import *\n')
        version = vinfo.version

    from pycbc import version
    version = version.version
    return version

class build_docs(Command):
    user_options = []
    description = "Build the documentation pages"
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        subprocess.check_call("cd docs; cp Makefile.std Makefile; cp conf_std.py conf.py; sphinx-apidoc "
                              " -o ./ -f -A 'PyCBC dev team' -V '0.1' ../pycbc && make html",
                            stderr=subprocess.STDOUT, shell=True)

class build_gh_pages(Command):
    user_options = []
    description = "Build the documentation pages for GitHub"
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        subprocess.check_call("mkdir -p _gh-pages/latest && touch _gh-pages/.nojekyll && "
                              "cd docs; cp Makefile.gh_pages Makefile; cp conf_std.py conf.py; sphinx-apidoc "
                              " -o ./ -f -A 'PyCBC dev team' -V '0.1' ../pycbc && make html",
                            stderr=subprocess.STDOUT, shell=True)

cmdclass = { 'build_docs' : build_docs,
             'build_gh_pages' : build_gh_pages,
             'clean' : clean,
             'build_ext':cbuild_ext
            }

extras_require = {'cuda': ['pycuda>=2015.1', 'scikit-cuda']}

# do the actual work of building the package
VERSION = get_version_info()

cythonext = ['waveform.spa_tmplt',
             'waveform.utils',
             'types.array',
             'filter.matchedfilter',
             'vetoes.chisq']
ext = []
for name in cythonext:
    e = Extension("pycbc.%s_cpu" % name,
                  ["pycbc/%s_cpu.pyx" % name.replace('.', '/')],
                  extra_compile_args=['-O3', '-w', '-msse4.2',
                                      '-ffast-math', '-ffinite-math-only'],
                  compiler_directives={'embedsignature': True})
    ext.append(e)

# Not all modules work like this:
e = Extension("pycbc.filter.fftw_pruned_cython",
              ["pycbc/filter/fftw_pruned_cython.pyx"],
              extra_compile_args=['-O3', '-w', '-msse4.2',
                                  '-ffast-math', '-ffinite-math-only'],
              compiler_directives={'embedsignature': True})
ext.append(e)
e = Extension("pycbc.events.eventmgr_cython",
              ["pycbc/events/eventmgr_cython.pyx"],
              extra_compile_args=['-O3', '-w', '-msse4.2',
                                  '-ffast-math', '-ffinite-math-only'],
              compiler_directives={'embedsignature': True})
ext.append(e)


setup (
    name = 'PyCBC',
    version = VERSION,
    description = 'Core library to analyze gravitational-wave data, find signals, and study their parameters.',
    long_description = open('descr.rst').read(),
    author = 'Ligo-Virgo Collaborations and the PyCBC team',
    author_email = 'alex.nitz@gmail.org',
    url = 'http://www.pycbc.org/',
    download_url = 'https://github.com/gwastro/pycbc/tarball/v%s' % VERSION,
    keywords = ['ligo', 'physics', 'gravity', 'signal processing', 'gravitational waves'],
    cmdclass = cmdclass,
    setup_requires = setup_requires,
    extras_require = extras_require,
    install_requires = install_requires,
    scripts  = find_files('bin', relpath='./') + ['tools/einsteinathome/pycbc_build_eah.sh'],
    packages = find_packages(),
    package_data = {'pycbc.workflow': find_files('pycbc/workflow'),
                    'pycbc.results': find_files('pycbc/results'),
                    'pycbc.tmpltbank': find_files('pycbc/tmpltbank')},
    ext_modules = ext,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Astronomy',
        'Topic :: Scientific/Engineering :: Physics',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    ],
)
