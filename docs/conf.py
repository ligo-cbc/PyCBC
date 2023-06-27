# -*- coding: utf-8 -*-
#
# PyCBC documentation build configuration file, created by
# sphinx-quickstart on Tue Jun 11 17:02:52 2013.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import os
import time
import pycbc.version
import subprocess
import glob

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.insert(0, os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest',
              'sphinx.ext.intersphinx', 'sphinx.ext.coverage',
              'sphinx.ext.viewcode', 'sphinxcontrib.programoutput',
              'sphinx.ext.napoleon', 'sphinx.ext.mathjax',
              'matplotlib.sphinxext.plot_directive', 'sphinx.ext.autosummary',
              'sphinx.ext.inheritance_diagram', 'sphinx_design',
              "sphinxcontrib.jquery",
              ]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'PyCBC'
copyright = u'2015, 2016, 2017, Alexander Nitz, Ian Harry, Christopher M. Biwer, Duncan A.  Brown, Josh Willis, and Tito Dal Canton'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = pycbc.version.last_release
# The full version, including alpha/beta/rc tags.
release = pycbc.version.version

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ['pycbc.']


# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
import sphinx_rtd_theme
html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {'style_nav_header_background': 'linear-gradient(0deg, rgba(0,0,0,1) 0%, rgba(193,193,255,1) 85%)',
                      'logo_only':True,
                      }

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

html_context = {
    'display_github': True,
    'github_user': 'gwastro',
    'github_repo': 'pycbc',
    'github_version': 'master/docs/',
    }

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = 'https://raw.githubusercontent.com/gwastro/pycbc-logo/master/pycbc_logo_name.png'

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
html_split_index = True

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'PyCBCdoc'


# -- Options for LaTeX output --------------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'PyCBC.tex', u'PyCBC Documentation',
   u'Alexander Nitz', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'pycbc', u'PyCBC Documentation',
     [u'Alexander Nitz'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'PyCBC', u'PyCBC Documentation',
   u'Alexander Nitz', 'PyCBC', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('http://docs.python.org/', None),
    'h5py': ('http://docs.h5py.org/en/stable/', None),
}

napoleon_use_ivar = False

suppress_warnings = ['image.nonlocal_uri']

# build the dynamic files in _include
def check_finished(proc):
    status = proc.poll()
    if status == 0:
        r = proc.returncode
        out = proc.stdout.read().decode()
        err = proc.stderr.read().decode()
        if r == 0:
            print('DONE with :{}'.format(' '.join(proc.args)))
        else:
            print(out, err, r)
            raise RuntimeError(f"Failure to run {fn}") 
        return True
    else:
        return False

def build_includes():
    """Creates rst files in the _include directory using the python scripts
    there.

    This will ignore any files in the _include directory that start with ``_``.
    """
    print("Running scripts in _include:")
    cwd = os.getcwd()
    os.chdir('_include')
    pyfiles = glob.glob('*.py') + glob.glob('*.sh')
    run_args = []
    for fn in pyfiles:
        if not fn.startswith('_'):
            if fn.endswith('.py'):
                exe = 'python'
            elif fn.endswith('.sh'):
                exe = 'bash'
             
            args = [exe, fn]
            run_args.append(args)
    
    run_num = 2
    i = 0
    running = []
    while i < len(run_args): 
        time.sleep(0.25)
        if len(running) < run_num:
            args = run_args[i]
            proc = subprocess.Popen(args,
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE)
            print('Running: {}'.format(' '.join(proc.args)))
            i += 1
            running.append(proc)

        for proc in running:
            if check_finished(proc):
                running.remove(proc)

    os.chdir(cwd)

if not 'SKIP_PYCBC_DOCS_INCLUDE' in os.environ:
    build_includes()

def setup(app):
    app.add_js_file('typed.min.js')
    app.add_js_file('terminal.css')
    app.add_js_file("theme_overrides.css")

# -- Options for inheritance graphs -------------------------------------------

# Makes the graphs be vertically aligned, with parents at the top
inheritance_graph_attrs = {'rankdir': 'TB'}
