# Copyright (C) 2016 Miriam Cabero Mueller
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
"""Module to generate figures with scatter plots and histograms.
"""

import numpy
import scipy.stats
import itertools
import matplotlib
matplotlib.use('agg')
from matplotlib import pyplot
import matplotlib.gridspec as gridspec
from pycbc.results import str_utils
#pyplot.rcParams.update({'text.usetex': True})

def create_axes_grid(parameters, labels=None):
    """Given a list of parameters, creates a figure with an axis for
    every possible combination of the parameters.

    Parameters
    ----------
    parameters : list
        Names of the variables to be plotted.
    labels : {None, list}, optional
        A list of names for the parameters.
    fiducial_figsize : {None, tuple}, optional
        Specify the default figure size to use. If the number of parameters
        is > 3, this will be scaled up. If None, will use (8,7).

    Returns
    -------
    fig : pyplot.figure
        The figure that was created.
    axis_dict : dict
        A dictionary mapping the parameter combinations to the axis and their
        location in the subplots grid; i.e., the key, values are:
        `{('param1', 'param2'): (pyplot.axes, row index, column index)}`
    """
    if labels is None:
        labels = parameters
    elif len(labels) != len(parameters):
        raise ValueError("labels and parameters must be same length")
    # Create figure with adequate size for number of parameters.
    ndim = len(parameters)
    if ndim < 3:
        fsize = (8, 7)
    else:
        fsize = (ndim*3 - 1, ndim*3 - 2)
    fig = pyplot.figure(figsize=fsize)
    gs = gridspec.GridSpec(ndim, ndim, wspace=0.05, hspace=0.05)
    # create grid of axis numbers to easily create axes in the right locations
    axes = numpy.arange(ndim**2).reshape((ndim, ndim))

    # Select possible combinations of plots and establish rows and columns.
    combos =  list(itertools.combinations(range(ndim),2))
    # add the diagonals
    combos += [(ii, ii) for ii in range(ndim)]

    # create the mapping between parameter combos and axes
    axis_dict = {}
    # cycle over all the axes, setting thing as needed
    for nrow in range(ndim):
        for ncolumn in range(ndim):
            ax = pyplot.subplot(gs[axes[nrow, ncolumn]])
            # map to a parameter index
            px = ncolumn
            py = nrow
            if (px, py) in combos:
                axis_dict[parameters[px], parameters[py]] = (ax, nrow, ncolumn)
                # x labels only on bottom
                if nrow + 1 == ndim:
                    ax.set_xlabel('{}'.format(labels[px]))
                else:
                    pyplot.setp(ax.get_xticklabels(), visible=False)
                # y labels only on left and non-diagonal
                if ncolumn == 0 and nrow != 0:
                    ax.set_ylabel('{}'.format(labels[py]))
                else:
                    pyplot.setp(ax.get_yticklabels(), visible=False)
            else:
                # make non-used axes invisible
                ax.axis('off')
    return fig, axis_dict

def get_scale_fac(fig, fiducial_width=8, fiducial_height=7):
    """Gets a factor to scale fonts by for the given figure. The scale
    factor is relative to a figure with dimensions
    (`fiducial_width`, `fiducial_height`).
    """
    width, height = fig.get_size_inches()
    return (width*height/(fiducial_width*fiducial_height))**0.5

def construct_kde(samples_array, use_kombine=False):
    """Constructs a KDE from the given samples.
    """
    if use_kombine:
        try:
            import kombine
        except ImportError:
            raise ImportError("kombine is not installed.")
    # construct the kde
    if use_kombine:
        kde = kombine.KDE(samples_array)
    else:
        kde = scipy.stats.gaussian_kde(samples_array.T)
    return kde


def create_density_plot(xparam, yparam, samples, plot_density=True,
        plot_contours=True, percentiles=None, cmap='viridis',
        contour_color='k', xmin=None, xmax=None, ymin=None, ymax=None,
        fig=None, ax=None, use_kombine=False):
    """Computes and plots posterior density and confidence intervals using the
    given samples.

    Parameters
    ----------
    xparam : string
        The parameter to plot on the x-axis.
    yparam : string
        The parameter to plot on the y-axis.
    samples : FieldArray
        A field array of the samples to plot.
    plot_density : {True, bool}
        Plot a color map of the density.
    plot_contours : {True, bool}
        Plot contours showing the n-th percentiles of the density.
    percentiles : {None, float or array}
        What percentile contours to draw. If None, will plot the 50th
        and 90th percentiles.
    cmap : {'viridis', string}
        The name of the colormap to use for the density plot.
    contour_color : {'k', string}
        What color to make the contours. Default is 'k'.
    xmin : {None, float}
        Minimum value to plot on x-axis.
    xmax : {None, float}
        Maximum value to plot on x-axis.
    ymin : {None, float}
        Minimum value to plot on y-axis.
    ymax : {None, float}
        Maximum value to plot on y-axis.
    fig : {None, pyplot.figure}
        Add the plot to the given figure. If None and ax is None, will create
        a new figure.
    ax : {None, pyplot.axes}
        Draw plot on the given axis. If None, will create a new axis from
        `fig`.
    use_kombine : {False, bool}
        Use kombine's KDE to calculate density. Otherwise, will use
        `scipy.stats.gaussian_kde.` Default is False.

    Returns
    -------
    fig : pyplot.figure
        The figure the plot was made on.
    ax : pyplot.axes
        The axes the plot was drawn on.
    """
    if percentiles is None:
        percentiles = numpy.array([50., 90.])
    percentiles = 100. - percentiles
    percentiles.sort()

    if ax is None and fig is None:
        fig = pyplot.figure()
    if ax is None:
        ax = fig.add_subplot(111)

    # convert samples to array and construct kde
    arr = samples.to_array(fields=[xparam, yparam], axis=-1)
    kde = construct_kde(arr, use_kombine=use_kombine)

    # construct grid to evaluate on
    if xmin is None:
        xmin = samples[xparam].min()
    if xmax is None:
        xmax = samples[xparam].max()
    if ymin is None:
        ymin = samples[yparam].min()
    if ymax is None:
        ymax = samples[yparam].max()
    npts = 100
    X, Y = numpy.mgrid[xmin:xmax:complex(0,npts), ymin:ymax:complex(0,npts)]
    pos = numpy.vstack([X.ravel(), Y.ravel()])
    if use_kombine:
        Z = numpy.exp(kde(pos.T).reshape(X.shape))
        draw = kde.draw
    else:
        Z = kde(pos).T.reshape(X.shape)
        draw = kde.resample

    # Exclude out-of-bound regions
    # this is a bit kludgy; should probably figure out a better solution
    # eventually for more than just m_p m_s
    bnds_mask = None
    if xparam == 'm_p' and yparam == 'm_s':
        bnds_mask = Y > X
    elif xparam == 'm_s' and yparam == 'm_p':
        bnds_mask = X > Y
    if bnds_mask is not None:
        Z[bnds_mask] = 0.

    if plot_density:
        im = ax.imshow(numpy.rot90(Z), extent=[xmin, xmax, ymin, ymax],
            aspect='auto', cmap=cmap, zorder=1)

    if plot_contours:
        # compute the percentile values
        resamps = kde(draw(int(npts**2)))
        if use_kombine:
            resamps = numpy.exp(resamps)
        s = numpy.percentile(resamps, percentiles)
        ct = ax.contour(X, Y, Z, s, colors=contour_color, zorder=3)
        # label contours
        lbls = ['{p}%'.format(p=int(p)) for p in (100. - percentiles)]
        fmt = dict(zip(ct.levels, lbls))
        fs = 8
        if fig is not None:
            # scale appropriately
            scale_fac = get_scale_fac(fig)
            fs *= scale_fac
        ax.clabel(ct, ct.levels, inline=True, fmt=fmt, fontsize=fs)

    return fig, ax


def create_marginalized_hist(ax, param, samples, percentiles=None, label=None,
        color='navy', filled=False, linecolor='b', title=True): 
    """Plots a 1D marginalized histogram of the given param from the given
    samples.

    Parameters
    ----------
    ax : pyplot.Axes
        The axes on which to draw the plot.
    param : string
        The parameter to plot.
    samples : FieldArray
        A field array of the samples to plot.
    percentiles : {None, float or array}
        What percentiles to draw lines at. If None, will draw lines at
        `[5, 50, 95]` (i.e., the bounds on the upper 90th percentile and the
        median).
    label : {None, string}
        A label for the parameter. If None, will use `param`.
    color : {'navy', string}
        What color to make the histogram; default is navy.
    filled : {False, bool}
        Whether to fill the histogram; default is False.
    linecolor : {'b', string}
        What color to use for the percentile lines.
    title : {True, bool}
        Add a title with the median value +/- uncertainty, with the
        max(min) `percentile` used for the +(-) uncertainty. 
    """
    if label is None:
        label = param
    if filled:
        htype = 'stepfilled'
    else:
        htype = 'step'
    values = samples[param]
    hp = ax.hist(values, bins=50, color=color, histtype=htype)
    if percentiles is None:
        percentiles = [5., 50., 95.]
    values = numpy.percentile(values, percentiles)
    for val in values:
        ax.axvline(x=val, ls='dashed', color=linecolor)
    if title:
        values_med = numpy.median(values)
        values_min = values.min()
        values_max = values.max()
        negerror = values_med - values_min
        poserror = values_max - values_med
        fmt = '$' + str_utils.format_value(values_med, negerror,
              plus_error=poserror, ndecs=2) + '$'
        ax.set_title('{} = {}'.format(label, fmt))
    # Remove y-ticks
    ax.set_yticks([])


def create_multidim_plot(
                parameters, samples, labels=None, mins=None, maxs=None,
                plot_marginal=True,
                plot_scatter=True,
                    zvals=None, show_colorbar=True, cbar_label=None,
                    vmin=None, vmax=None, scatter_cmap='plasma_r',
                plot_density=False, plot_contours=True,
                    density_cmap='viridis', contour_color='k',
                    use_kombine=False):
    """Generate a figure with several plots and histograms.

    Parameters
    ----------
    parameters: list
        Names of the variables to be plotted.
    samples : FieldArray
        A field array of the samples to plot.
    labels: {None, list}, optional
        A list of names for the parameters.
    mins : {None, dict}, optional
        Minimum value for the axis of each variable in `parameters`.
        If None, it will use the minimum of the corresponding variable in
        `samples`.
    maxs : {None, dict}, optional
        Maximum value for the axis of each variable in `parameters`.
        If None, it will use the maximum of the corresponding variable in
        `samples`.
    plot_marginal : {True, bool}
        Plot the marginalized distribution on the diagonals. If False, the
        diagonal axes will be turned off.
    plot_scatter : {True, bool}
        Plot each sample point as a scatter plot.
    zvals : {None, array}
        An array to use for coloring the scatter plots. If None, scatter points
        will be the same color.
    show_colorbar : {True, bool}
        Show the colorbar of zvalues used for the scatter points. A ValueError
        will be raised if zvals is None and this is True.
    cbar_label : {None, str}
        Specify a label to add to the colorbar.
    vmin: {None, float}, optional
        Minimum value for the colorbar. If None, will use the minimum of zvals.
    vmax: {None, float}, optional
        Maximum value for the colorbar. If None, will use the maxmimum of
        zvals.
    scatter_cmap : {'plasma_r', string}
        The color map to use for the scatter points. Default is 'plasma_r'.
    plot_density : {False, bool}
        Plot the density of points as a color map.
    plot_contours : {True, bool}
        Draw contours showing the 50th and 90th percentile confidence regions.
    density_cmap : {'viridis', string}
        The color map to use for the density plot.
    contour_color : {'k', string}
        The color to use for the contour lines.
    use_kombine : {False, bool}
        Use kombine's KDE to calculate density. Otherwise, will use
        `scipy.stats.gaussian_kde.` Default is False.

    Returns
    -------
    fig : pyplot.figure
        The figure that was created.
    axis_dict : dict
        A dictionary mapping the parameter combinations to the axis and their
        location in the subplots grid; i.e., the key, values are:
        `{('param1', 'param2'): (pyplot.axes, row index, column index)}`
    """

    if labels is None:
        labels = parameters

    # set up the figure with a grid of axes
    fig, axis_dict = create_axes_grid(parameters, labels=labels)

    # turn labels into a dict for easier access
    labels = dict(zip(parameters, labels))

    # values for axis bounds
    if mins is None:
        mins = {p:samples[p].min() for p in parameters}
    if maxs is None:
        maxs = {p:samples[p].max() for p in parameters}

    # Diagonals...
    for param in parameters:
        ax, nrow, ncol = axis_dict[param, param]
        # plot marginal...
        if plot_marginal:
            create_marginalized_hist(ax, param, samples, label=labels[param],
                    color='navy', filled=False, linecolor='b', title=True)
        # ... or turn off
        else:
            ax.axis('off')

    # Off-diagonals...
    for px, py in axis_dict:
        if px == py:
            continue
        ax, _, _ = axis_dict[px, py]
        if plot_scatter:
            # Sort zvals to get higher values on top in scatter plots
            if zvals is not None:
                sort_indices = zvals.argsort()
                zvals = zvals[sort_indices]
                samples = samples[sort_indices]
            else:
                # use the 0th part of the scatter cmap for the color
                zvals = numpy.zeros(samples.size)
            if plot_density:
                alpha = 0.3
            else:
                alpha = 1.
            plt = ax.scatter(x=samples[px], y=samples[py], c=zvals, s=5, 
                        edgecolors='none', vmin=vmin, vmax=vmax,
                        cmap=scatter_cmap, alpha=alpha, zorder=2)

        if plot_contours or plot_density:
            create_density_plot(px, py, samples, plot_density=plot_density,
                    plot_contours=plot_contours, cmap=density_cmap,
                    contour_color=contour_color, xmin=mins[px], xmax=maxs[px],
                    ymin=mins[py], ymax=maxs[py], ax=ax,
                    use_kombine=use_kombine)

        ax.set_xlim(mins[px], maxs[px])
        ax.set_ylim(mins[py], maxs[py])

    # adjust tick number for large number of plots
    if len(parameters) > 3:
        for px, py in axis_dict:
            ax, _, _ = axis_dict[px, py]
            ax.set_xticks(reduce_ticks(ax, 'x', maxticks=3))
            ax.set_yticks(reduce_ticks(ax, 'y', maxticks=3))

    if plot_scatter and show_colorbar:
        # compute font size based on fig size
        scale_fac = get_scale_fac(fig)
        fig.subplots_adjust(right=0.85, wspace=0.03)
        cbar_ax = fig.add_axes([0.9, 0.1, 0.03, 0.8])
        cb = fig.colorbar(plt, cax=cbar_ax)
        if cbar_label is not None:
            cb.set_label(cbar_label, fontsize=12*scale_fac)
        cb.ax.tick_params(labelsize=8*scale_fac)

    return fig, axis_dict


def reduce_ticks(ax, which, maxticks=3):
    """Given a pyplot axis, resamples its `which`-axis ticks such that are at most
    `maxticks` left.

    Parameters
    ----------
    ax : axis
        The axis to adjust.
    which : {'x' | 'y'}
        Which axis to adjust.
    maxticks : {3, int}
        Maximum number of ticks to use.

    Returns
    -------
    array
        An array of the selected ticks.
    """
    ticks = getattr(ax, 'get_{}ticks'.format(which))()
    if len(ticks) > maxticks:
        # make sure the left/right value is not at the edge
        minax, maxax = getattr(ax, 'get_{}lim'.format(which))()
        dw = abs(maxax-minax)/10.
        start_idx, end_idx = 0, len(ticks)
        if ticks[0] < minax + dw:
            start_idx += 1
        if ticks[-1] > maxax - dw:
            end_idx -= 1
        # get reduction factor
        fac = int(len(ticks) / maxticks)
        ticks = ticks[start_idx:end_idx:fac]
    return ticks
