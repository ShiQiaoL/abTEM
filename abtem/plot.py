from colorsys import hls_to_rgb

import matplotlib.pyplot as plt
import numpy as np
from ase.data import covalent_radii
from ase.data.colors import cpk_colors
from matplotlib.patches import Circle
from matplotlib.patches import Rectangle
from abtem.transfer import calculate_polar_aberrations, calculate_aperture, calculate_temporal_envelope, \
    calculate_spatial_envelope, calculate_gaussian_envelope

cube = np.array([[[0, 0, 0], [0, 0, 1]],
                 [[0, 0, 0], [0, 1, 0]],
                 [[0, 0, 0], [1, 0, 0]],
                 [[0, 0, 1], [0, 1, 1]],
                 [[0, 0, 1], [1, 0, 1]],
                 [[0, 1, 0], [1, 1, 0]],
                 [[0, 1, 0], [0, 1, 1]],
                 [[1, 0, 0], [1, 1, 0]],
                 [[1, 0, 0], [1, 0, 1]],
                 [[0, 1, 1], [1, 1, 1]],
                 [[1, 0, 1], [1, 1, 1]],
                 [[1, 1, 0], [1, 1, 1]]])


def plane2axes(plane):
    axes = ()
    last_axis = [0, 1, 2]
    for axis in list(plane):
        if axis == 'x':
            axes += (0,)
            last_axis.remove(0)
        if axis == 'y':
            axes += (1,)
            last_axis.remove(1)
        if axis == 'z':
            axes += (2,)
            last_axis.remove(2)
    return axes + (last_axis[0],)


def plot_atoms(atoms, repeat=(1, 1), scan_area=None, plane='xy', ax=None, scale_atoms=.5, numbering=False):
    if ax is None:
        fig, ax = plt.subplots()

    axes = plane2axes(plane)

    atoms = atoms.copy()
    cell = atoms.cell
    atoms *= repeat + (1,)

    for line in cube:
        cell_lines = np.array([np.dot(line[0], cell), np.dot(line[1], cell)])
        ax.plot(cell_lines[:, axes[0]], cell_lines[:, axes[1]], 'k-')

    if len(atoms) > 0:
        positions = atoms.positions[:, axes[:2]]
        order = np.argsort(atoms.positions[:, axes[2]])
        positions = positions[order]

        colors = cpk_colors[atoms.numbers[order]]
        sizes = covalent_radii[atoms.numbers[order]] * scale_atoms

        for position, size, color in zip(positions, sizes, colors):
            ax.add_patch(Circle(position, size, facecolor=color, edgecolor='black'))

        ax.axis('equal')
        ax.set_xlabel(plane[0])
        ax.set_ylabel(plane[1])

        if numbering:
            for i, (position, size) in enumerate(zip(positions, sizes)):
                ax.annotate('{}'.format(i), xy=position, ha="center", va="center")

    if scan_area is not None:
        ax.add_patch(Rectangle(xy=scan_area[0],
                               width=scan_area[1][0] - scan_area[0][0],
                               height=scan_area[1][1] - scan_area[0][1], alpha=.33, color='k'))


def plot_ctf(ctf, max_k, ax=None, phi=0, n=1000):
    k = np.linspace(0, max_k, n)
    alpha = k * ctf.wavelength
    aberrations = calculate_polar_aberrations(alpha, phi, ctf.wavelength, ctf._parameters)
    aperture = calculate_aperture(alpha, ctf.semiangle_cutoff, ctf.rolloff)
    temporal_envelope = calculate_temporal_envelope(alpha, ctf.wavelength, ctf.focal_spread)
    spatial_envelope = calculate_spatial_envelope(alpha, phi, ctf.wavelength, ctf.angular_spread, ctf.parameters)
    gaussian_envelope = calculate_gaussian_envelope(alpha, ctf.wavelength, ctf.gaussian_spread)
    envelope = aperture * temporal_envelope * spatial_envelope * gaussian_envelope

    if ax is None:
        ax = plt.subplot()

    ax.plot(k, aberrations.imag * envelope, label='CTF')

    if ctf.semiangle_cutoff < np.inf:
        ax.plot(k, aperture, label='Aperture')

    if ctf.focal_spread > 0.:
        ax.plot(k, temporal_envelope, label='Temporal envelope')

    if ctf.angular_spread > 0.:
        ax.plot(k, spatial_envelope, label='Spatial envelope')

    if ctf.gaussian_spread > 0.:
        #print(gaussian_envelope)
        ax.plot(k, gaussian_envelope, label='Gaussian envelope')

    if not np.allclose(envelope, 1.):
        ax.plot(k, envelope, label='Product envelope')

    ax.set_xlabel('k [1 / Å]')
    ax.legend()


def _prepare_array(waves, i=0, space='real', scale='linear', logscale_constant=.1, convert=None, ):
    try:
        waves = waves.build()
    except AttributeError:
        pass

    array = waves.array

    if len(array.shape) == 3:
        array = array[i]

    if space == 'fourier':
        array = np.fft.fftshift(np.fft.fft2(array))

    elif space != 'real':
        raise RuntimeError('space must be "real" or "fourier"')

    if scale == 'log':
        array = np.log(1 + logscale_constant * array)

    elif scale != 'linear':
        raise RuntimeError('scale must be "log" or "linear"')

    if (convert is not None):
        array = convert_complex(array, output=convert)

    elif (convert is None) & np.iscomplexobj(array):
        array = convert_complex(array, output='intensity')

    return array


def plot_profile(waves, i=0, ax=None, space='real', scale='linear', logscale_constant=.1, convert=None, title=None,
                 **kwargs):
    array = _prepare_array(waves, i=i, space=space, scale=scale, logscale_constant=logscale_constant, convert=convert)

    y = array[array.shape[0] // 2]

    if space == 'fourier':
        x_label = 'kx [1 / Å]'
        fourier_limits = waves.fourier_limits.ravel()
        x = np.linspace(fourier_limits[0], fourier_limits[1], len(y))

    else:
        x_label = 'x [Å]'
        x = np.linspace(0, waves.extent[0], len(y))

    if ax is None:
        ax = plt.subplot()

    ax.plot(x, y, **kwargs)
    ax.set_xlabel(x_label)

    if title is not None:
        ax.set_title(title)


def plot_image(waves, i=0, ax=None, space='real', scale='linear', logscale_constant=.1, convert=None, title=None,
               cmap='gray', **kwargs):
    array = _prepare_array(waves, i=i, space=space, scale=scale, logscale_constant=logscale_constant, convert=convert)

    if space == 'fourier':
        x_label = 'kx [1 / Å]'
        y_label = 'ky [1 / Å]'
        extent = waves.fourier_limits.ravel()

    else:
        x_label = 'x [Å]'
        y_label = 'y [Å]'
        extent = [0, waves.extent[0], 0, waves.extent[1]]

    if ax is None:
        ax = plt.subplot()

    ax.imshow(array.T, extent=extent, cmap=cmap, origin='lower', **kwargs)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

    if title is not None:
        ax.set_title(title)


def domain_coloring(z, fade_to_white=False, saturation=1, k=.5):
    h = (np.angle(z) + np.pi) / (2 * np.pi) + 0.5
    if fade_to_white:
        l = k ** np.abs(z)
    else:
        l = 1 - k ** np.abs(z)
    c = np.vectorize(hls_to_rgb)(h, l, saturation)
    c = np.array(c).T

    c = (c - c.min()) / c.ptp()

    return c
