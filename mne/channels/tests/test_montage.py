# Author: Teon Brooks <teon.brooks@gmail.com>
#         Stefan Appelhoff <stefan.appelhoff@mailbox.org>
#
# License: BSD (3-clause)

import os
import os.path as op

import pytest

import numpy as np
from scipy.io import savemat
from copy import deepcopy
from functools import partial
from string import ascii_lowercase

from numpy.testing import (assert_array_equal, assert_almost_equal,
                           assert_allclose, assert_array_almost_equal,
                           assert_array_less, assert_equal)

from mne import create_info, EvokedArray, read_evokeds, __file__ as _mne_file
from mne.channels import (Montage, read_montage, read_dig_montage,
                          get_builtin_montages, DigMontage,
                          read_dig_egi, read_dig_captrack, read_dig_fif)
from mne.channels.montage import _set_montage, make_dig_montage
from mne.channels.montage import transform_to_head
from mne.channels import read_polhemus_fastscan, read_dig_polhemus_isotrak
from mne.channels import compute_dev_head_t

from mne.channels._dig_montage_utils import _transform_to_head_call
from mne.channels._dig_montage_utils import _fix_data_fiducials
from mne.channels._dig_montage_utils import _get_fid_coords
from mne.utils import (_TempDir, run_tests_if_main, assert_dig_allclose,
                       object_diff, Bunch)
from mne.bem import _fit_sphere
from mne.transforms import apply_trans, get_ras_to_neuromag_trans
from mne.io.constants import FIFF
from mne._digitization import Digitization
from mne._digitization._utils import _read_dig_points, _format_dig_points
from mne._digitization.base import _get_dig_eeg, _count_points_by_type

from mne.viz._3d import _fiducial_coords

from mne.io.kit import read_mrk
from mne.io import (read_raw_brainvision, read_raw_egi, read_raw_fif,
                    read_raw_cnt, read_raw_edf, read_raw_nicolet, read_raw_bdf,
                    read_raw_eeglab, read_fiducials, __file__ as _mne_io_file)

from mne.datasets import testing


data_path = testing.data_path(download=False)
fif_dig_montage_fname = op.join(data_path, 'montage', 'eeganes07.fif')
egi_dig_montage_fname = op.join(data_path, 'montage', 'coordinates.xml')
egi_raw_fname = op.join(data_path, 'montage', 'egi_dig_test.raw')
egi_fif_fname = op.join(data_path, 'montage', 'egi_dig_raw.fif')
bvct_dig_montage_fname = op.join(data_path, 'montage', 'captrak_coords.bvct')
bv_raw_fname = op.join(data_path, 'montage', 'bv_dig_test.vhdr')
bv_fif_fname = op.join(data_path, 'montage', 'bv_dig_raw.fif')
locs_montage_fname = op.join(data_path, 'EEGLAB', 'test_chans.locs')
evoked_fname = op.join(data_path, 'montage', 'level2_raw-ave.fif')
eeglab_fname = op.join(data_path, 'EEGLAB', 'test_raw.set')
bdf_fname1 = op.join(data_path, 'BDF', 'test_generator_2.bdf')
bdf_fname2 = op.join(data_path, 'BDF', 'test_bdf_stim_channel.bdf')
egi_fname1 = op.join(data_path, 'EGI', 'test_egi.mff')
cnt_fname = op.join(data_path, 'CNT', 'scan41_short.cnt')

io_dir = op.dirname(_mne_io_file)
kit_dir = op.join(io_dir, 'kit', 'tests', 'data')
elp = op.join(kit_dir, 'test_elp.txt')
hsp = op.join(kit_dir, 'test_hsp.txt')
hpi = op.join(kit_dir, 'test_mrk.sqd')
bv_fname = op.join(io_dir, 'brainvision', 'tests', 'data', 'test.vhdr')
fif_fname = op.join(io_dir, 'tests', 'data', 'test_raw.fif')
edf_path = op.join(io_dir, 'edf', 'tests', 'data', 'test.edf')
bdf_path = op.join(io_dir, 'edf', 'tests', 'data', 'test_bdf_eeglab.mat')
egi_fname2 = op.join(io_dir, 'egi', 'tests', 'data', 'test_egi.raw')
vhdr_path = op.join(io_dir, 'brainvision', 'tests', 'data', 'test.vhdr')
ctf_fif_fname = op.join(io_dir, 'tests', 'data', 'test_ctf_comp_raw.fif')
nicolet_fname = op.join(io_dir, 'nicolet', 'tests', 'data',
                        'test_nicolet_raw.data')


def test_fiducials():
    """Test handling of fiducials."""
    # Eventually the code used here should be unified with montage.py, but for
    # now it uses code in odd places
    for fname in (fif_fname, ctf_fif_fname):
        fids, coord_frame = read_fiducials(fname)
        points = _fiducial_coords(fids, coord_frame)
        assert points.shape == (3, 3)
        # Fids
        assert_allclose(points[:, 2], 0., atol=1e-6)
        assert_allclose(points[::2, 1], 0., atol=1e-6)
        assert points[2, 0] > 0  # RPA
        assert points[0, 0] < 0  # LPA
        # Nasion
        assert_allclose(points[1, 0], 0., atol=1e-6)
        assert points[1, 1] > 0


def test_documented():
    """Test that montages are documented."""
    docs = read_montage.__doc__
    lines = [line[4:] for line in docs.splitlines()]
    start = stop = None
    for li, line in enumerate(lines):
        if line.startswith('====') and li < len(lines) - 2 and \
                lines[li + 1].startswith('Kind') and\
                lines[li + 2].startswith('===='):
            start = li + 3
        elif start is not None and li > start and line.startswith('===='):
            stop = li
            break
    assert (start is not None)
    assert (stop is not None)
    kinds = [line.split(' ')[0] for line in lines[start:stop]]
    kinds = [kind for kind in kinds if kind != '']
    montages = os.listdir(op.join(op.dirname(_mne_file), 'channels', 'data',
                                  'montages'))
    montages = sorted(op.splitext(m)[0] for m in montages)
    assert_equal(len(set(montages)), len(montages))
    assert_equal(len(set(kinds)), len(kinds), err_msg=str(sorted(kinds)))
    assert_equal(set(montages), set(kinds))


def test_montage():
    """Test making montages."""
    tempdir = _TempDir()
    inputs = dict(
        sfp='FidNz 0       9.071585155     -2.359754454\n'
            'FidT9 -6.711765       0.040402876     -3.251600355\n'
            'very_very_very_long_name -5.831241498 -4.494821698  4.955347697\n'
            'Cz 0       0       8.899186843',
        csd='// MatLab   Sphere coordinates [degrees]         Cartesian coordinates\n'  # noqa: E501
            '// Label       Theta       Phi    Radius         X         Y         Z       off sphere surface\n'  # noqa: E501
            'E1      37.700     -14.000       1.000    0.7677    0.5934   -0.2419  -0.00000000000000011\n'  # noqa: E501
            'E3      51.700      11.000       1.000    0.6084    0.7704    0.1908   0.00000000000000000\n'  # noqa: E501
            'E31      90.000     -11.000       1.000    0.0000    0.9816   -0.1908   0.00000000000000000\n'  # noqa: E501
            'E61     158.000     -17.200       1.000   -0.8857    0.3579   -0.2957  -0.00000000000000022',  # noqa: E501
        mm_elc='# ASA electrode file\nReferenceLabel  avg\nUnitPosition    mm\n'  # noqa:E501
               'NumberPositions=    68\n'
               'Positions\n'
               '-86.0761 -19.9897 -47.9860\n'
               '85.7939 -20.0093 -48.0310\n'
               '0.0083 86.8110 -39.9830\n'
               '-86.0761 -24.9897 -67.9860\n'
               'Labels\nLPA\nRPA\nNz\nDummy\n',
        m_elc='# ASA electrode file\nReferenceLabel  avg\nUnitPosition    m\n'
              'NumberPositions=    68\nPositions\n-.0860761 -.0199897 -.0479860\n'  # noqa:E501
              '.0857939 -.0200093 -.0480310\n.0000083 .00868110 -.0399830\n'
              '.08 -.02 -.04\n'
              'Labels\nLPA\nRPA\nNz\nDummy\n',
        txt='Site  Theta  Phi\n'
            'Fp1  -92    -72\n'
            'Fp2   92     72\n'
            'very_very_very_long_name       -92     72\n'
            'O2        92    -90\n',
        elp='346\n'
            'EEG\t      F3\t -62.027\t -50.053\t      85\n'
            'EEG\t      Fz\t  45.608\t      90\t      85\n'
            'EEG\t      F4\t   62.01\t  50.103\t      85\n'
            'EEG\t      FCz\t   68.01\t  58.103\t      85\n',
        hpts='eeg Fp1 -95.0 -3. -3.\n'
             'eeg AF7 -1 -1 -3\n'
             'eeg A3 -2 -2 2\n'
             'eeg A 0 0 0',
        bvef='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<!-- Generated by EasyCap Configurator 19.05.2014 -->\n'
             '<Electrodes defaults="false">\n'
             '  <Electrode>\n'
             '    <Name>Fp1</Name>\n'
             '    <Theta>-90</Theta>\n'
             '    <Phi>-72</Phi>\n'
             '    <Radius>1</Radius>\n'
             '    <Number>1</Number>\n'
             '  </Electrode>\n'
             '  <Electrode>\n'
             '    <Name>Fz</Name>\n'
             '    <Theta>45</Theta>\n'
             '    <Phi>90</Phi>\n'
             '    <Radius>1</Radius>\n'
             '    <Number>2</Number>\n'
             '  </Electrode>\n'
             '  <Electrode>\n'
             '    <Name>F3</Name>\n'
             '    <Theta>-60</Theta>\n'
             '    <Phi>-51</Phi>\n'
             '    <Radius>1</Radius>\n'
             '    <Number>3</Number>\n'
             '  </Electrode>\n'
             '  <Electrode>\n'
             '    <Name>F7</Name>\n'
             '    <Theta>-90</Theta>\n'
             '    <Phi>-36</Phi>\n'
             '    <Radius>1</Radius>\n'
             '    <Number>4</Number>\n'
             '  </Electrode>\n'
             '</Electrodes>',
    )
    # Get actual positions and save them for checking
    # csd comes from the string above, all others come from commit 2fa35d4
    poss = dict(
        sfp=[[0.0, 9.07159, -2.35975], [-6.71176, 0.0404, -3.2516],
             [-5.83124, -4.49482, 4.95535], [0.0, 0.0, 8.89919]],
        mm_elc=[[-0.08608, -0.01999, -0.04799], [0.08579, -0.02001, -0.04803],
                [1e-05, 0.08681, -0.03998], [-0.08608, -0.02499, -0.06799]],
        m_elc=[[-0.08608, -0.01999, -0.04799], [0.08579, -0.02001, -0.04803],
               [1e-05, 0.00868, -0.03998], [0.08, -0.02, -0.04]],
        txt=[[-26.25044, 80.79056, -2.96646], [26.25044, 80.79056, -2.96646],
             [-26.25044, -80.79056, -2.96646], [0.0, -84.94822, -2.96646]],
        elp=[[-48.20043, 57.55106, 39.86971], [0.0, 60.73848, 59.4629],
             [48.1426, 57.58403, 39.89198], [41.64599, 66.91489, 31.8278]],
        hpts=[[-95, -3, -3], [-1, -1., -3.], [-2, -2, 2.], [0, 0, 0]],
        bvef=[[-2.62664445e-02,  8.08398039e-02,  5.20474890e-18],
              [3.68031324e-18,  6.01040764e-02,  6.01040764e-02],
              [-4.63256329e-02,  5.72073923e-02,  4.25000000e-02],
              [-6.87664445e-02,  4.99617464e-02,  5.20474890e-18]],
    )
    for key, text in inputs.items():
        kind = key.split('_')[-1]
        fname = op.join(tempdir, 'test.' + kind)
        with open(fname, 'w') as fid:
            fid.write(text)
        unit = 'mm' if kind == 'bvef' else 'm'
        montage = read_montage(fname, unit=unit)
        if kind in ('sfp', 'txt'):
            assert ('very_very_very_long_name' in montage.ch_names)
        assert_equal(len(montage.ch_names), 4)
        assert_equal(len(montage.ch_names), len(montage.pos))
        assert_equal(montage.pos.shape, (4, 3))
        assert_equal(montage.kind, 'test')
        if kind == 'csd':
            dtype = [('label', 'S4'), ('theta', 'f8'), ('phi', 'f8'),
                     ('radius', 'f8'), ('x', 'f8'), ('y', 'f8'), ('z', 'f8'),
                     ('off_sph', 'f8')]
            try:
                table = np.loadtxt(fname, skip_header=2, dtype=dtype)
            except TypeError:
                table = np.loadtxt(fname, skiprows=2, dtype=dtype)
            poss['csd'] = np.c_[table['x'], table['y'], table['z']]
        if kind == 'elc':
            # Make sure points are reasonable distance from geometric centroid
            centroid = np.sum(montage.pos, axis=0) / montage.pos.shape[0]
            distance_from_centroid = np.apply_along_axis(
                np.linalg.norm, 1,
                montage.pos - centroid)
            assert_array_less(distance_from_centroid, 0.2)
            assert_array_less(0.01, distance_from_centroid)
        assert_array_almost_equal(poss[key], montage.pos, 4, err_msg=key)

    # Bvef is either auto or mm in terms of "units"
    with pytest.raises(ValueError, match='be "auto" or "mm" for .bvef files.'):
        bvef_file = op.join(tempdir, 'test.' + 'bvef')
        read_montage(bvef_file, unit='m')

    # Test reading in different letter case.
    ch_names = ["F3", "FZ", "F4", "FC3", "FCz", "FC4", "C3", "CZ", "C4", "CP3",
                "CPZ", "CP4", "P3", "PZ", "P4", "O1", "OZ", "O2"]
    montage = read_montage('standard_1020', ch_names=ch_names)
    assert_array_equal(ch_names, montage.ch_names)

    # test transform
    input_strs = ["""
    eeg Fp1 -95.0 -31.0 -3.0
    eeg AF7 -81 -59 -3
    eeg AF3 -87 -41 28
    cardinal 2 -91 0 -42
    cardinal 1 0 -91 -42
    cardinal 3 0 91 -42
    """, """
    Fp1 -95.0 -31.0 -3.0
    AF7 -81 -59 -3
    AF3 -87 -41 28
    FidNz -91 0 -42
    FidT9 0 -91 -42
    FidT10 0 91 -42
    """]
    # sfp files seem to have Nz, T9, and T10 as fiducials:
    # https://github.com/mne-tools/mne-python/pull/4482#issuecomment-321980611

    kinds = ['test_fid.hpts', 'test_fid.sfp']

    for kind, input_str in zip(kinds, input_strs):
        fname = op.join(tempdir, kind)
        with open(fname, 'w') as fid:
            fid.write(input_str)
        montage = read_montage(op.join(tempdir, kind), transform=True)

        # check coordinate transformation
        pos = np.array([-95.0, -31.0, -3.0])
        nasion = np.array([-91, 0, -42])
        lpa = np.array([0, -91, -42])
        rpa = np.array([0, 91, -42])
        fids = np.vstack((nasion, lpa, rpa))
        trans = get_ras_to_neuromag_trans(fids[0], fids[1], fids[2])
        pos = apply_trans(trans, pos)
        assert_array_equal(montage.pos[0], pos)
        assert_array_equal(montage.nasion[[0, 2]], [0, 0])
        assert_array_equal(montage.lpa[[1, 2]], [0, 0])
        assert_array_equal(montage.rpa[[1, 2]], [0, 0])
        pos = np.array([-95.0, -31.0, -3.0])
        montage_fname = op.join(tempdir, kind)
        montage = read_montage(montage_fname, unit='mm')
        assert_array_equal(montage.pos[0], pos * 1e-3)

        # test with last
        info = create_info(montage.ch_names, 1e3,
                           ['eeg'] * len(montage.ch_names))
        _set_montage(info, montage)
        pos2 = np.array([c['loc'][:3] for c in info['chs']])
        assert_array_equal(pos2, montage.pos)
        assert_equal(montage.ch_names, info['ch_names'])

        info = create_info(
            montage.ch_names, 1e3, ['eeg'] * len(montage.ch_names))

        evoked = EvokedArray(
            data=np.zeros((len(montage.ch_names), 1)), info=info, tmin=0)

        # test return type as well as set montage
        assert (isinstance(evoked.set_montage(montage), type(evoked)))

        pos3 = np.array([c['loc'][:3] for c in evoked.info['chs']])
        assert_array_equal(pos3, montage.pos)
        assert_equal(montage.ch_names, evoked.info['ch_names'])

        # Warning should be raised when some EEG are not specified in montage
        info = create_info(montage.ch_names + ['foo', 'bar'], 1e3,
                           ['eeg'] * (len(montage.ch_names) + 2))
        with pytest.warns(RuntimeWarning, match='position specified'):
            _set_montage(info, montage)

    # Channel names can be treated case insensitive
    info = create_info(['FP1', 'af7', 'AF3'], 1e3, ['eeg'] * 3)
    _set_montage(info, montage)

    # Unless there is a collision in names
    info = create_info(['FP1', 'Fp1', 'AF3'], 1e3, ['eeg'] * 3)
    assert (info['dig'] is None)
    with pytest.warns(RuntimeWarning, match='position specified'):
        _set_montage(info, montage)
    assert len(info['dig']) == 5  # 2 EEG w/pos, 3 fiducials
    montage.ch_names = ['FP1', 'Fp1', 'AF3']
    info = create_info(['fp1', 'AF3'], 1e3, ['eeg', 'eeg'])
    assert (info['dig'] is None)
    with pytest.warns(RuntimeWarning, match='position specified'):
        _set_montage(info, montage, set_dig=False)
    assert (info['dig'] is None)

    # test get_pos2d method
    montage = read_montage("standard_1020")
    c3 = montage.get_pos2d()[montage.ch_names.index("C3")]
    c4 = montage.get_pos2d()[montage.ch_names.index("C4")]
    fz = montage.get_pos2d()[montage.ch_names.index("Fz")]
    oz = montage.get_pos2d()[montage.ch_names.index("Oz")]
    f1 = montage.get_pos2d()[montage.ch_names.index("F1")]
    assert (c3[0] < 0)  # left hemisphere
    assert (c4[0] > 0)  # right hemisphere
    assert (fz[1] > 0)  # frontal
    assert (oz[1] < 0)  # occipital
    assert_allclose(fz[0], 0, atol=1e-2)  # midline
    assert_allclose(oz[0], 0, atol=1e-2)  # midline
    assert (f1[0] < 0 and f1[1] > 0)  # left frontal

    # test get_builtin_montages function
    montages = get_builtin_montages()
    assert (len(montages) > 0)  # MNE should always ship with montages
    assert ("standard_1020" in montages)  # 10/20 montage
    assert ("standard_1005" in montages)  # 10/05 montage


@testing.requires_testing_data
def test_read_locs():
    """Test reading EEGLAB locs."""
    pos = read_montage(locs_montage_fname).pos
    expected = [[0., 9.99779165e-01, -2.10157875e-02],
                [3.08738197e-01, 7.27341573e-01, -6.12907052e-01],
                [-5.67059636e-01, 6.77066318e-01, 4.69067752e-01],
                [0., 7.14575231e-01, 6.99558616e-01]]
    assert_allclose(pos[:4], expected, atol=1e-7)


def test_read_dig_montage():
    """Test read_dig_montage."""
    names = ['nasion', 'lpa', 'rpa', '1', '2', '3', '4', '5']
    montage = read_dig_montage(hsp, hpi, elp, names, transform=False)
    elp_points = _read_dig_points(elp)
    hsp_points = _read_dig_points(hsp)
    hpi_points = read_mrk(hpi)
    with pytest.deprecated_call():
        assert_equal(montage.point_names, names)
        assert_array_equal(montage.elp, elp_points)
        assert_array_equal(montage.hsp, hsp_points)
    assert (montage.dev_head_t is None)
    montage = read_dig_montage(hsp, hpi, elp, names,
                               transform=True, dev_head_t=True)
    # check coordinate transformation
    # nasion
    with pytest.deprecated_call():
        assert_almost_equal(montage.nasion[0], 0)
        assert_almost_equal(montage.nasion[2], 0)
    # lpa and rpa
    with pytest.deprecated_call():
        assert_allclose(montage.lpa[1:], 0, atol=1e-16)
        assert_allclose(montage.rpa[1:], 0, atol=1e-16)
    # device head transform

    EXPECTED_DEV_HEAD_T = np.array(
        [[-3.72201691e-02, -9.98212167e-01, -4.67667497e-02, -7.31583414e-04],
         [8.98064989e-01, -5.39382685e-02, 4.36543170e-01, 1.60134431e-02],
         [-4.38285221e-01, -2.57513699e-02, 8.98466990e-01, 6.13035748e-02],
         [0.00000000e+00, 0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]
    )
    assert_allclose(montage.dev_head_t, EXPECTED_DEV_HEAD_T, atol=1e-7)

    # Digitizer as array
    with pytest.deprecated_call():
        m2 = read_dig_montage(hsp_points, hpi_points, elp_points, names,
                              unit='m')
        assert_array_equal(m2.hsp, montage.hsp)
        m3 = read_dig_montage(hsp_points * 1000, hpi_points, elp_points * 1000,
                              names)
    with pytest.deprecated_call():
        assert_allclose(m3.hsp, montage.hsp)

    # test unit parameter and .mat support
    tempdir = _TempDir()
    mat_hsp = op.join(tempdir, 'test.mat')
    savemat(mat_hsp, dict(Points=(1000 * hsp_points).T), oned_as='row')
    montage_cm = read_dig_montage(mat_hsp, hpi, elp, names, unit='cm')
    with pytest.deprecated_call():
        assert_allclose(montage_cm.hsp, montage.hsp * 10.)
        assert_allclose(montage_cm.elp, montage.elp * 10.)
    pytest.raises(ValueError, read_dig_montage, hsp, hpi, elp, names,
                  unit='km')
    # extra columns
    extra_hsp = op.join(tempdir, 'test.txt')
    with open(hsp, 'rb') as fin:
        with open(extra_hsp, 'wb') as fout:
            for line in fin:
                if line.startswith(b'%'):
                    fout.write(line)
                else:
                    # extra column
                    fout.write(line.rstrip() + b' 0.0 0.0 0.0\n')
    with pytest.warns(RuntimeWarning, match='Found .* columns instead of 3'):
        montage_extra = read_dig_montage(extra_hsp, hpi, elp, names)
    with pytest.deprecated_call():
        assert_allclose(montage_extra.hsp, montage.hsp)
        assert_allclose(montage_extra.elp, montage.elp)


def test_read_dig_montage_using_polhemus_fastscan():
    """Test FastScan."""
    N_EEG_CH = 10

    my_electrode_positions = read_polhemus_fastscan(
        op.join(kit_dir, 'test_elp.txt')
    )

    montage = make_dig_montage(
        # EEG_CH
        ch_pos=dict(zip(ascii_lowercase[:N_EEG_CH],
                        np.random.RandomState(0).rand(N_EEG_CH, 3))),
        # NO NAMED points
        nasion=my_electrode_positions[0],
        lpa=my_electrode_positions[1],
        rpa=my_electrode_positions[2],
        hpi=my_electrode_positions[3:],
        hsp=read_polhemus_fastscan(op.join(kit_dir, 'test_hsp.txt')),

        # Other defaults
        coord_frame='unknown'
    )

    assert montage.__repr__() == (
        '<DigMontage | '
        '500 extras (headshape), 5 HPIs, 3 fiducials, 10 channels>'
    )  # XXX: is this wrong? extra is not in headspace, is it?

    assert set([d['coord_frame'] for d in montage.dig]) == {
        FIFF.FIFFV_COORD_UNKNOWN
    }  # XXX: so far we build everything in 'unknown'

    EXPECTED_FID_IN_POLHEMUS = {
        'nasion': [0.001393, 0.0131613, -0.0046967],
        'lpa': [-0.0624997, -0.0737271, 0.07996],
        'rpa': [-0.0748957, 0.0873785, 0.0811943],
    }
    fiducials, fid_coordframe = _get_fid_coords(montage.dig)
    assert fid_coordframe == FIFF.FIFFV_COORD_UNKNOWN
    for kk, val in fiducials.items():
        assert_allclose(val, EXPECTED_FID_IN_POLHEMUS[kk])


def test_read_dig_montage_using_polhemus_fastscan_error_handling(tmpdir):
    """Test reading Polhemus FastSCAN errors."""
    with open(op.join(kit_dir, 'test_elp.txt')) as fid:
        content = fid.read().replace('FastSCAN', 'XxxxXXXX')

    fname = str(tmpdir.join('faulty_FastSCAN.txt'))
    with open(fname, 'w') as fid:
        fid.write(content)

    with pytest.raises(ValueError, match='not contain Polhemus FastSCAN'):
        _ = read_polhemus_fastscan(fname)

    EXPECTED_ERR_MSG = "allowed value is '.txt', but got '.bar' instead"
    with pytest.raises(ValueError, match=EXPECTED_ERR_MSG):
        _ = read_polhemus_fastscan(fname=tmpdir.join('foo.bar'))


def test_read_dig_polhemus_isotrak_hsp():
    """Test reading Polhemus IsoTrak HSP file."""
    EXPECTED_FID_IN_POLHEMUS = {
        'nasion': np.array([1.1056e-01, -5.4210e-19, 0]),
        'lpa': np.array([-2.1075e-04, 8.0793e-02, -7.5894e-19]),
        'rpa': np.array([2.1075e-04, -8.0793e-02, -2.8731e-18]),
    }
    montage = read_dig_polhemus_isotrak(fname=op.join(kit_dir, 'test.hsp'),
                                        ch_names=None)
    assert montage.__repr__() == (
        '<DigMontage | '
        '500 extras (headshape), 0 HPIs, 3 fiducials, 0 channels>'
    )

    fiducials, fid_coordframe = _get_fid_coords(montage.dig)

    assert fid_coordframe == FIFF.FIFFV_COORD_UNKNOWN
    for kk, val in fiducials.items():
        assert_array_equal(val, EXPECTED_FID_IN_POLHEMUS[kk])


def test_read_dig_polhemus_isotrak_elp():
    """Test reading Polhemus IsoTrak ELP file."""
    EXPECTED_FID_IN_POLHEMUS = {
        'nasion': np.array([1.1056e-01, -5.4210e-19, 0]),
        'lpa': np.array([-2.1075e-04, 8.0793e-02, -7.5894e-19]),
        'rpa': np.array([2.1075e-04, -8.0793e-02, -2.8731e-18]),
    }
    montage = read_dig_polhemus_isotrak(fname=op.join(kit_dir, 'test.elp'),
                                        ch_names=None)
    assert montage.__repr__() == (
        '<DigMontage | '
        '0 extras (headshape), 5 HPIs, 3 fiducials, 0 channels>'
    )
    fiducials, fid_coordframe = _get_fid_coords(montage.dig)

    assert fid_coordframe == FIFF.FIFFV_COORD_UNKNOWN
    for kk, val in fiducials.items():
        assert_array_equal(val, EXPECTED_FID_IN_POLHEMUS[kk])


@pytest.fixture(scope='module')
def isotrak_eeg(tmpdir_factory):
    """Mock isotrak file with EEG positions."""
    _SEED = 42
    N_ROWS, N_COLS = 5, 3
    content = np.random.RandomState(_SEED).randn(N_ROWS, N_COLS)

    fname = tmpdir_factory.mktemp('data').join('test.eeg')
    with open(str(fname), 'w') as fid:
        fid.write((
            '3	200\n'
            '//Shape file\n'
            '//Minor revision number\n'
            '2\n'
            '//Subject Name\n'
            '%N	Name    \n'
            '////Shape code, number of digitized points\n'
        ))
        fid.write('0 {rows:d}\n'.format(rows=N_ROWS))
        fid.write((
            '//Position of fiducials X+, Y+, Y- on the subject\n'
            '%F	0.11056	-5.421e-19	0	\n'
            '%F	-0.00021075	0.080793	-7.5894e-19	\n'
            '%F	0.00021075	-0.080793	-2.8731e-18	\n'
            '//No of rows, no of columns; position of digitized points\n'
        ))
        fid.write('{rows:d} {cols:d}\n'.format(rows=N_ROWS, cols=N_COLS))
        for row in content:
            fid.write('\t'.join('%0.18e' % cell for cell in row) + '\n')

    return str(fname)


def test_read_dig_polhemus_isotrak_eeg(isotrak_eeg):
    """Test reading Polhemus IsoTrak EEG positions."""
    N_CHANNELS = 5
    _SEED = 42
    EXPECTED_FID_IN_POLHEMUS = {
        'nasion': np.array([1.1056e-01, -5.4210e-19, 0]),
        'lpa': np.array([-2.1075e-04, 8.0793e-02, -7.5894e-19]),
        'rpa': np.array([2.1075e-04, -8.0793e-02, -2.8731e-18]),
    }
    ch_names = ['eeg {:01d}'.format(ii) for ii in range(N_CHANNELS)]
    EXPECTED_CH_POS = dict(zip(
        ch_names, np.random.RandomState(_SEED).randn(N_CHANNELS, 3)))

    montage = read_dig_polhemus_isotrak(fname=isotrak_eeg, ch_names=ch_names)
    assert montage.__repr__() == (
        '<DigMontage | '
        '0 extras (headshape), 0 HPIs, 3 fiducials, 5 channels>'
    )

    fiducials, fid_coordframe = _get_fid_coords(montage.dig)

    assert fid_coordframe == FIFF.FIFFV_COORD_UNKNOWN
    for kk, val in fiducials.items():
        assert_array_equal(val, EXPECTED_FID_IN_POLHEMUS[kk])

    for kk, dig_point in zip(montage.ch_names, _get_dig_eeg(montage.dig)):
        assert_array_equal(dig_point['r'], EXPECTED_CH_POS[kk])
        assert dig_point['coord_frame'] == FIFF.FIFFV_COORD_UNKNOWN


def test_read_dig_polhemus_isotrak_error_handling(isotrak_eeg, tmpdir):
    """Test errors in reading Polhemus IsoTrak files.

    1 - matching ch_names and number of points in isotrak file.
    2 - error for unsupported file extensions.
    """
    # Check ch_names
    N_CHANNELS = 5
    EXPECTED_ERR_MSG = "not match the number of points.*Expected.*5, given 47"
    with pytest.raises(ValueError, match=EXPECTED_ERR_MSG):
        _ = read_dig_polhemus_isotrak(
            fname=isotrak_eeg,
            ch_names=['eeg {:01d}'.format(ii) for ii in range(N_CHANNELS + 42)]
        )

    # Check fname extensions
    fname = op.join(tmpdir, 'foo.bar')
    with pytest.raises(
        ValueError,
        match="Allowed val.*'.hsp', '.elp' and '.eeg', but got '.bar' instead"
    ):
        _ = read_dig_polhemus_isotrak(fname=fname, ch_names=None)


def test_combining_digmontage_objects():
    """Test combining different DigMontage objects."""
    rng = np.random.RandomState(0)
    fiducials = dict(zip(('nasion', 'lpa', 'rpa'), rng.rand(3, 3)))

    # hsp positions are [1X, 1X, 1X]
    hsp1 = make_dig_montage(**fiducials, hsp=np.full((2, 3), 11.))
    hsp2 = make_dig_montage(**fiducials, hsp=np.full((2, 3), 12.))
    hsp3 = make_dig_montage(**fiducials, hsp=np.full((2, 3), 13.))

    # hpi positions are [2X, 2X, 2X]
    hpi1 = make_dig_montage(**fiducials, hpi=np.full((2, 3), 21.))
    hpi2 = make_dig_montage(**fiducials, hpi=np.full((2, 3), 22.))
    hpi3 = make_dig_montage(**fiducials, hpi=np.full((2, 3), 23.))

    # channels have positions at 40s, 50s, and 60s.
    ch_pos1 = make_dig_montage(
        **fiducials,
        ch_pos={'h': [41, 41, 41], 'b': [42, 42, 42], 'g': [43, 43, 43]}
    )
    ch_pos2 = make_dig_montage(
        **fiducials,
        ch_pos={'n': [51, 51, 51], 'y': [52, 52, 52], 'p': [53, 53, 53]}
    )
    ch_pos3 = make_dig_montage(
        **fiducials,
        ch_pos={'v': [61, 61, 61], 'a': [62, 62, 62], 'l': [63, 63, 63]}
    )

    montage = (
        DigMontage() + hsp1 + hsp2 + hsp3 + hpi1 + hpi2 + hpi3 + ch_pos1 +
        ch_pos2 + ch_pos3
    )
    assert montage.__repr__() == (
        '<DigMontage | '
        '6 extras (headshape), 6 HPIs, 3 fiducials, 9 channels>'
    )

    EXPECTED_MONTAGE = make_dig_montage(
        **fiducials,
        hsp=np.concatenate([np.full((2, 3), 11.), np.full((2, 3), 12.),
                            np.full((2, 3), 13.)]),
        hpi=np.concatenate([np.full((2, 3), 21.), np.full((2, 3), 22.),
                            np.full((2, 3), 23.)]),
        ch_pos={
            'h': [41, 41, 41], 'b': [42, 42, 42], 'g': [43, 43, 43],
            'n': [51, 51, 51], 'y': [52, 52, 52], 'p': [53, 53, 53],
            'v': [61, 61, 61], 'a': [62, 62, 62], 'l': [63, 63, 63],
        }
    )

    # Do some checks to ensure they are the same DigMontage
    assert len(montage.ch_names) == len(EXPECTED_MONTAGE.ch_names)
    assert all([c in montage.ch_names for c in EXPECTED_MONTAGE.ch_names])
    actual_occurrences = _count_points_by_type(montage.dig)
    expected_occurrences = _count_points_by_type(EXPECTED_MONTAGE.dig)
    assert actual_occurrences == expected_occurrences


def test_combining_digmontage_forbiden_behaviors():
    """Test combining different DigMontage objects with repeated names."""
    rng = np.random.RandomState(0)
    fiducials = dict(zip(('nasion', 'lpa', 'rpa'), rng.rand(3, 3)))
    dig1 = make_dig_montage(
        **fiducials,
        ch_pos=dict(zip(list('abc'), rng.rand(3, 3))),
    )
    dig2 = make_dig_montage(
        **fiducials,
        ch_pos=dict(zip(list('bcd'), rng.rand(3, 3))),
    )
    dig2_wrong_fid = make_dig_montage(
        nasion=rng.rand(3), lpa=rng.rand(3), rpa=rng.rand(3),
        ch_pos=dict(zip(list('ghi'), rng.rand(3, 3))),
    )
    dig2_wrong_coordframe = make_dig_montage(
        **fiducials,
        ch_pos=dict(zip(list('ghi'), rng.rand(3, 3))),
        coord_frame='meg'
    )

    EXPECTED_ERR_MSG = "Cannot.*duplicated channel.*found: \'b\', \'c\'."
    with pytest.raises(RuntimeError, match=EXPECTED_ERR_MSG):
        _ = dig1 + dig2

    with pytest.raises(RuntimeError, match='fiducial locations do not match'):
        _ = dig1 + dig2_wrong_fid

    with pytest.raises(RuntimeError, match='not in the same coordinate '):
        _ = dig1 + dig2_wrong_coordframe


def test_set_dig_montage():
    """Test applying DigMontage to inst."""
    # Extensive testing of applying `dig` to info is done in test_meas_info
    # with `test_make_dig_points`.
    names = ['nasion', 'lpa', 'rpa', '1', '2', '3', '4', '5']
    hsp_points = _read_dig_points(hsp)
    elp_points = _read_dig_points(elp)
    nasion, lpa, rpa = elp_points[:3]
    nm_trans = get_ras_to_neuromag_trans(nasion, lpa, rpa)
    elp_points = apply_trans(nm_trans, elp_points)
    nasion, lpa, rpa = elp_points[:3]
    hsp_points = apply_trans(nm_trans, hsp_points)

    montage = read_dig_montage(hsp, hpi, elp, names, transform=True,
                               dev_head_t=True)
    temp_dir = _TempDir()
    fname_temp = op.join(temp_dir, 'test.fif')
    montage.save(fname_temp)
    with pytest.deprecated_call():
        montage_read = read_dig_montage(fif=fname_temp)
    for use_mon in (montage, montage_read):
        info = create_info(['Test Ch'], 1e3, ['eeg'])
        with pytest.warns(None):  # warns on one run about not all positions
            _set_montage(info, use_mon)
        hs = np.array([p['r'] for i, p in enumerate(info['dig'])
                       if p['kind'] == FIFF.FIFFV_POINT_EXTRA])
        nasion_dig = np.array([p['r'] for p in info['dig']
                               if all([p['ident'] == FIFF.FIFFV_POINT_NASION,
                                       p['kind'] == FIFF.FIFFV_POINT_CARDINAL])
                               ])
        lpa_dig = np.array([p['r'] for p in info['dig']
                            if all([p['ident'] == FIFF.FIFFV_POINT_LPA,
                                    p['kind'] == FIFF.FIFFV_POINT_CARDINAL])])
        rpa_dig = np.array([p['r'] for p in info['dig']
                            if all([p['ident'] == FIFF.FIFFV_POINT_RPA,
                                    p['kind'] == FIFF.FIFFV_POINT_CARDINAL])])
        hpi_dig = np.array([p['r'] for p in info['dig']
                            if p['kind'] == FIFF.FIFFV_POINT_HPI])
        assert_allclose(hs, hsp_points, atol=1e-7)
        assert_allclose(nasion_dig.ravel(), nasion, atol=1e-7)
        assert_allclose(lpa_dig.ravel(), lpa, atol=1e-7)
        assert_allclose(rpa_dig.ravel(), rpa, atol=1e-7)
        assert_allclose(hpi_dig, elp_points[3:], atol=1e-7)


@testing.requires_testing_data
def test_fif_dig_montage():
    """Test FIF dig montage support."""
    with pytest.deprecated_call():
        dig_montage = read_dig_montage(fif=fif_dig_montage_fname)

    # test round-trip IO
    temp_dir = _TempDir()
    fname_temp = op.join(temp_dir, 'test.fif')
    _check_roundtrip(dig_montage, fname_temp)

    # Make a BrainVision file like the one the user would have had
    raw_bv = read_raw_brainvision(bv_fname, preload=True)
    raw_bv_2 = raw_bv.copy()
    mapping = dict()
    for ii, ch_name in enumerate(raw_bv.ch_names):
        mapping[ch_name] = 'EEG%03d' % (ii + 1,)
    raw_bv.rename_channels(mapping)
    for ii, ch_name in enumerate(raw_bv_2.ch_names):
        mapping[ch_name] = 'EEG%03d' % (ii + 33,)
    raw_bv_2.rename_channels(mapping)
    raw_bv.add_channels([raw_bv_2])

    for ii in range(2):
        # Set the montage
        raw_bv.set_montage(dig_montage)

        # Check the result
        evoked = read_evokeds(evoked_fname)[0]

        assert_equal(len(raw_bv.ch_names), len(evoked.ch_names) - 1)
        for ch_py, ch_c in zip(raw_bv.info['chs'], evoked.info['chs'][:-1]):
            assert_equal(ch_py['ch_name'],
                         ch_c['ch_name'].replace('EEG ', 'EEG'))
            # C actually says it's unknown, but it's not (?):
            # assert_equal(ch_py['coord_frame'], ch_c['coord_frame'])
            assert_equal(ch_py['coord_frame'], FIFF.FIFFV_COORD_HEAD)
            c_loc = ch_c['loc'].copy()
            c_loc[c_loc == 0] = np.nan
            assert_allclose(ch_py['loc'], c_loc, atol=1e-7)
        assert_dig_allclose(raw_bv.info, evoked.info)

    # Roundtrip of non-FIF start
    names = ['nasion', 'lpa', 'rpa', '1', '2', '3', '4', '5']
    montage = read_dig_montage(hsp, hpi, elp, names, transform=False)
    pytest.raises(RuntimeError, montage.save, fname_temp)  # must be head coord
    montage = read_dig_montage(hsp, hpi, elp, names)
    _check_roundtrip(montage, fname_temp)

    # Test old way matches new way
    with pytest.deprecated_call():
        dig_montage = read_dig_montage(fif=fif_dig_montage_fname)
    dig_montage_fif = read_dig_fif(fif_dig_montage_fname)
    assert dig_montage.dig == dig_montage_fif.dig
    assert object_diff(dig_montage.ch_names, dig_montage_fif.ch_names) == ''


@testing.requires_testing_data
def test_egi_dig_montage():
    """Test EGI MFF XML dig montage support."""
    with pytest.deprecated_call():
        dig_montage = read_dig_montage(egi=egi_dig_montage_fname, unit='m')

    # # test round-trip IO
    temp_dir = _TempDir()
    fname_temp = op.join(temp_dir, 'egi_test.fif')
    _check_roundtrip(dig_montage, fname_temp)

    with pytest.deprecated_call():
        # Test coordinate transform
        # dig_montage.transform_to_head()  # XXX: this call had no effect!!
        # nasion
        assert_almost_equal(dig_montage.nasion[0], 0)
        assert_almost_equal(dig_montage.nasion[2], 0)
        # lpa and rpa
        assert_allclose(dig_montage.lpa[1:], 0, atol=1e-16)
        assert_allclose(dig_montage.rpa[1:], 0, atol=1e-16)

    # Test accuracy and embedding within raw object
    raw_egi = read_raw_egi(egi_raw_fname, channel_naming='EEG %03d')
    raw_egi.set_montage(dig_montage)
    test_raw_egi = read_raw_fif(egi_fif_fname)

    assert_equal(len(raw_egi.ch_names), len(test_raw_egi.ch_names))
    for ch_raw, ch_test_raw in zip(raw_egi.info['chs'],
                                   test_raw_egi.info['chs']):
        assert_equal(ch_raw['ch_name'], ch_test_raw['ch_name'])
        assert_equal(ch_raw['coord_frame'], FIFF.FIFFV_COORD_HEAD)
        assert_allclose(ch_raw['loc'], ch_test_raw['loc'], atol=1e-7)
    assert_dig_allclose(raw_egi.info, test_raw_egi.info)

    # Test old way matches new way
    with pytest.deprecated_call():
        dig_montage = read_dig_montage(egi=egi_dig_montage_fname, unit='m')
    dig_montage_egi = read_dig_egi(egi_dig_montage_fname)
    dig_montage_egi = transform_to_head(dig_montage_egi)
    assert dig_montage.dig == dig_montage_egi.dig
    assert object_diff(dig_montage.ch_names, dig_montage_egi.ch_names) == ''


@testing.requires_testing_data
def test_bvct_dig_montage_old_api():  # XXX: to remove in 0.20
    """Test BrainVision CapTrak XML dig montage support."""
    with pytest.warns(RuntimeWarning, match='Using "m" as unit for BVCT file'):
        read_dig_montage(bvct=bvct_dig_montage_fname, unit='m')

    with pytest.deprecated_call():
        dig_montage = read_dig_montage(bvct=bvct_dig_montage_fname)

    # test round-trip IO
    temp_dir = _TempDir()
    fname_temp = op.join(temp_dir, 'bvct_test.fif')
    _check_roundtrip(dig_montage, fname_temp)

    with pytest.deprecated_call():
        # nasion
        assert_almost_equal(dig_montage.nasion[0], 0)
        assert_almost_equal(dig_montage.nasion[2], 0)
        # lpa and rpa
        assert_allclose(dig_montage.lpa[1:], 0, atol=1e-16)
        assert_allclose(dig_montage.rpa[1:], 0, atol=1e-16)

    # Test accuracy and embedding within raw object
    raw_bv = read_raw_brainvision(bv_raw_fname)
    with pytest.warns(RuntimeWarning, match='Did not set.*channel pos'):
        raw_bv.set_montage(dig_montage)
    test_raw_bv = read_raw_fif(bv_fif_fname)

    assert_equal(len(raw_bv.ch_names), len(test_raw_bv.ch_names))
    for ch_raw, ch_test_raw in zip(raw_bv.info['chs'],
                                   test_raw_bv.info['chs']):
        assert_equal(ch_raw['ch_name'], ch_test_raw['ch_name'])
        assert_equal(ch_raw['coord_frame'], FIFF.FIFFV_COORD_HEAD)
        assert_allclose(ch_raw['loc'], ch_test_raw['loc'], atol=1e-7)
    assert_dig_allclose(raw_bv.info, test_raw_bv.info)


@testing.requires_testing_data
def test_read_dig_captrack(tmpdir):
    """Test reading a captrack montage file."""
    EXPECTED_CH_NAMES = [
        'AF3', 'AF4', 'AF7', 'AF8', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'CP1',
        'CP2', 'CP3', 'CP4', 'CP5', 'CP6', 'CPz', 'Cz', 'F1', 'F2', 'F3', 'F4',
        'F5', 'F6', 'F7', 'F8', 'FC1', 'FC2', 'FC3', 'FC4', 'FC5', 'FC6',
        'FT10', 'FT7', 'FT8', 'FT9', 'Fp1', 'Fp2', 'Fz', 'O1', 'O2', 'Oz',
        'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'PO10', 'PO3', 'PO4',
        'PO7', 'PO8', 'PO9', 'POz', 'Pz', 'T7', 'T8', 'TP10', 'TP7', 'TP8',
        'TP9'
    ]
    montage = read_dig_captrack(
        fname=op.join(data_path, 'montage', 'captrak_coords.bvct')
    )

    assert montage.ch_names == EXPECTED_CH_NAMES
    assert montage.__repr__() == (
        '<DigMontage | '
        '0 extras (headshape), 0 HPIs, 3 fiducials, 64 channels>'
    )

    montage = transform_to_head(montage)  # transform_to_head has to be tested
    _check_roundtrip(montage=montage, fname=str(tmpdir.join('bvct_test.fif')))

    with pytest.deprecated_call():
        assert_allclose(
            actual=np.array([montage.nasion, montage.lpa, montage.rpa]),
            desired=[[0, 0.11309, 0], [-0.09189, 0, 0], [0.09240, 0, 0]],
            atol=1e-5,
        )

    # I think that comparing dig should be enough. cc: @sappelhoff
    raw_bv = read_raw_brainvision(bv_raw_fname)
    with pytest.warns(RuntimeWarning, match='Did not set 3 channel pos'):
        raw_bv.set_montage(montage)
    test_raw_bv = read_raw_fif(bv_fif_fname)

    assert_dig_allclose(raw_bv.info, test_raw_bv.info)


def test_set_montage():
    """Test setting a montage."""
    raw = read_raw_fif(fif_fname)
    orig_pos = np.array([ch['loc'][:3] for ch in raw.info['chs']
                         if ch['ch_name'].startswith('EEG')])
    raw.set_montage('mgh60')  # test loading with string argument
    new_pos = np.array([ch['loc'][:3] for ch in raw.info['chs']
                        if ch['ch_name'].startswith('EEG')])
    assert ((orig_pos != new_pos).all())
    r0 = _fit_sphere(new_pos)[1]
    assert_allclose(r0, [0., -0.016, 0.], atol=1e-3)
    # mgh70 has no 61/62/63/64 (these are EOG/ECG)
    mon = read_montage('mgh70')
    assert 'EEG061' not in mon.ch_names
    assert 'EEG074' in mon.ch_names


# XXX: this does not check ch_names + it cannot work because of write_dig
def _check_roundtrip(montage, fname):
    """Check roundtrip writing."""
    with pytest.deprecated_call():
        assert_equal(montage.coord_frame, 'head')
    montage.save(fname)
    montage_read = read_dig_fif(fname=fname)
    assert_equal(str(montage), str(montage_read))
    with pytest.deprecated_call():
        for kind in ('elp', 'hsp', 'nasion', 'lpa', 'rpa'):
            if getattr(montage, kind, None) is not None:
                assert_allclose(getattr(montage, kind),
                                getattr(montage_read, kind), err_msg=kind)
    with pytest.deprecated_call():
        assert_equal(montage_read.coord_frame, 'head')


def _fake_montage(ch_names):
    return Montage(
        pos=np.random.RandomState(42).randn(len(ch_names), 3),
        ch_names=ch_names,
        kind='foo',
        selection=np.arange(len(ch_names))
    )


cnt_ignore_warns = [
    pytest.mark.filterwarnings(
        'ignore:.*Could not parse meas date from the header. Setting to None.'
    ),
    pytest.mark.filterwarnings((
        'ignore:.*Could not define the number of bytes automatically.'
        ' Defaulting to 2.')
    ),
]


@testing.requires_testing_data
@pytest.mark.parametrize('read_raw,fname', [
    pytest.param(partial(read_raw_nicolet, ch_type='eeg'),
                 nicolet_fname,
                 id='nicolet'),
    pytest.param(read_raw_eeglab, eeglab_fname, id='eeglab'),
    pytest.param(read_raw_edf, edf_path, id='edf'),
    pytest.param(read_raw_bdf, bdf_path,
                 marks=pytest.mark.xfail(raises=NotImplementedError),
                 id='bdf 1'),
    pytest.param(read_raw_bdf, bdf_fname1, id='bdf 2'),
    pytest.param(read_raw_bdf, bdf_fname2, id='bdf 3'),
    pytest.param(read_raw_egi, egi_fname1, id='egi mff'),
    pytest.param(read_raw_egi, egi_fname2,
                 marks=pytest.mark.filterwarnings('ignore:.*than one event'),
                 id='egi raw'),
    pytest.param(partial(read_raw_cnt, eog='auto', misc=['NA1', 'LEFT_EAR']),
                 cnt_fname, marks=cnt_ignore_warns, id='cnt'),
    pytest.param(read_raw_brainvision, vhdr_path, id='brainvision'),
])
def test_montage_when_reading_and_setting(read_raw, fname):
    """Test montage.

    This is a regression test to help refactor Digitization.
    """
    with pytest.deprecated_call():
        raw_none = read_raw(fname, montage=None, preload=False)
    # raw_none_copy = deepcopy(raw_none)
    montage = _fake_montage(raw_none.info['ch_names'])

    with pytest.deprecated_call():
        raw_montage = read_raw(fname, montage=montage, preload=False)

    raw_none.set_montage(montage)

    # Check that reading with montage or setting the montage is the same
    assert_array_equal(raw_none.get_data(), raw_montage.get_data())
    assert object_diff(raw_none.info['dig'], raw_montage.info['dig']) == ''
    assert object_diff(raw_none.info['chs'], raw_montage.info['chs']) == ''


@testing.requires_testing_data
@pytest.mark.parametrize('read_raw,fname', [
    pytest.param(partial(read_raw_nicolet, ch_type='eeg'),
                 nicolet_fname,
                 marks=pytest.mark.skip,
                 id='nicolet'),
    pytest.param(read_raw_eeglab, eeglab_fname,
                 marks=pytest.mark.skip,
                 id='eeglab'),
    pytest.param(read_raw_edf, edf_path, id='edf'),
    pytest.param(read_raw_bdf, bdf_path,
                 marks=pytest.mark.xfail(raises=NotImplementedError),
                 id='bdf 1'),
    pytest.param(read_raw_bdf, bdf_fname1, id='bdf 2'),
    pytest.param(read_raw_bdf, bdf_fname2, id='bdf 3'),
    pytest.param(read_raw_egi, egi_fname1,
                 marks=pytest.mark.skip,
                 id='egi mff'),
    pytest.param(read_raw_egi, egi_fname2,
                 marks=pytest.mark.filterwarnings('ignore:.*than one event'),
                 id='egi raw'),
    pytest.param(partial(read_raw_cnt, eog='auto', misc=['NA1', 'LEFT_EAR']),
                 cnt_fname,
                 marks=[*cnt_ignore_warns, pytest.mark.skip],
                 id='cnt'),
    pytest.param(read_raw_brainvision, vhdr_path,
                 marks=pytest.mark.skip,
                 id='brainvision'),
])
def test_montage_when_reading_and_setting_more(read_raw, fname):
    """Test montage.

    This is a regression test to help refactor Digitization.
    """
    with pytest.deprecated_call():
        raw_none = read_raw(fname, montage=None, preload=False)
    raw_none_copy = deepcopy(raw_none)

    # check consistency between reading and setting with montage=None
    assert raw_none_copy.info['dig'] is None
    original_chs = deepcopy(raw_none_copy.info['chs'])
    original_loc = np.array([ch['loc'] for ch in original_chs])
    assert_array_equal(original_loc, np.zeros_like(original_loc))

    raw_none_copy.set_montage(montage=None)
    loc = np.array([ch['loc'] for ch in raw_none_copy.info['chs']])
    assert_array_equal(loc, np.full_like(loc, np.NaN))

EXPECTED_DIG_RPR = [
    '<DigPoint |        LPA : (-6.7, 0.0, -3.3) mm      : head frame>',  # FidT9 [-6.711765    0.04040288 -3.25160035]  # noqa
    '<DigPoint |     Nasion : (0.0, 9.1, -2.4) mm       : head frame>',  # FidNz [ 0.          9.07158515 -2.35975445]  # noqa
    '<DigPoint |        RPA : (6.7, 0.0, -3.3) mm       : head frame>',  # FidT10 [ 6.711765    0.04040288 -3.25160035] # noqa
    '<DigPoint |     EEG #1 : (-2.7, 8.9, 1.1) mm       : head frame>',  # E1 [-2.69540556  8.88482032  1.08830814]     # noqa
    '<DigPoint |     EEG #2 : (2.7, 8.9, 1.1) mm        : head frame>',  # E2 [2.69540556 8.88482032 1.08830814]        # noqa
    '<DigPoint |     EEG #3 : (-4.5, 6.0, 4.4) mm       : head frame>',  # E3 [-4.45938719  6.02115996  4.36532148]     # noqa
    '<DigPoint |     EEG #4 : (4.5, 6.0, 4.4) mm        : head frame>',  # E4 [4.45938719 6.02115996 4.36532148]        # noqa
    '<DigPoint |     EEG #5 : (-5.5, 0.3, 6.4) mm       : head frame>',  # E5 [-5.47913021  0.28494865  6.38332782]     # noqa
    '<DigPoint |     EEG #6 : (5.5, 0.3, 6.4) mm        : head frame>',  # E6 [5.47913021 0.28494865 6.38332782]        # noqa
    '<DigPoint |     EEG #7 : (-5.8, -4.5, 5.0) mm      : head frame>',  # E7 [-5.8312415 -4.4948217  4.9553477]        # noqa
    '<DigPoint |     EEG #8 : (5.8, -4.5, 5.0) mm       : head frame>',  # E8 [ 5.8312415 -4.4948217  4.9553477]        # noqa
    '<DigPoint |     EEG #9 : (-2.7, -8.6, 0.2) mm      : head frame>',  # E9 [-2.73883802 -8.60796685  0.23936822]     # noqa
    '<DigPoint |    EEG #10 : (2.7, -8.6, 0.2) mm       : head frame>',  # E10 [ 2.73883802 -8.60796685  0.23936822]    # noqa
    '<DigPoint |    EEG #11 : (-6.4, 4.1, -0.4) mm      : head frame>',  # E11 [-6.3990872   4.12724888 -0.35685224]    # noqa
    '<DigPoint |    EEG #12 : (6.4, 4.1, -0.4) mm       : head frame>',  # E12 [ 6.3990872   4.12724888 -0.35685224]    # noqa
    '<DigPoint |    EEG #13 : (-7.3, -1.9, -0.6) mm     : head frame>',  # E13 [-7.3046251  -1.86623801 -0.62918201]    # noqa
    '<DigPoint |    EEG #14 : (7.3, -1.9, -0.6) mm      : head frame>',  # E14 [ 7.3046251  -1.86623801 -0.62918201]    # noqa
    '<DigPoint |    EEG #15 : (-6.0, -5.8, 0.1) mm      : head frame>',  # E15 [-6.03474684 -5.7557822   0.05184301]    # noqa
    '<DigPoint |    EEG #16 : (6.0, -5.8, 0.1) mm       : head frame>',  # E16 [ 6.03474684 -5.7557822   0.05184301]    # noqa
    '<DigPoint |    EEG #17 : (0.0, 8.0, 5.0) mm        : head frame>',  # E17 [0.         7.96264703 5.044718  ]       # noqa
    '<DigPoint |    EEG #18 : (0.0, 9.3, -2.2) mm       : head frame>',  # E18 [ 0.          9.2711397  -2.21151643]    # noqa
    '<DigPoint |    EEG #19 : (0.0, -6.7, 6.5) mm       : head frame>',  # E19 [ 0.         -6.67669403  6.46520826]    # noqa
    '<DigPoint |    EEG #20 : (0.0, -9.0, 0.5) mm       : head frame>',  # E20 [ 0.         -8.9966865   0.48795205]    # noqa
    '<DigPoint |    EEG #21 : (-6.5, 2.4, -5.3) mm      : head frame>',  # E21 [-6.51899513  2.4172994  -5.25363707]    # noqa
    '<DigPoint |    EEG #22 : (6.5, 2.4, -5.3) mm       : head frame>',  # E22 [ 6.51899513  2.4172994  -5.25363707]    # noqa
    '<DigPoint |    EEG #23 : (-6.2, -2.5, -5.6) mm     : head frame>',  # E23 [-6.17496939 -2.45813888 -5.637381  ]    # noqa
    '<DigPoint |    EEG #24 : (6.2, -2.5, -5.6) mm      : head frame>',  # E24 [ 6.17496939 -2.45813888 -5.637381  ]    # noqa
    '<DigPoint |    EEG #25 : (-3.8, -6.4, -5.3) mm     : head frame>',  # E25 [-3.78498391 -6.40101441 -5.26004069]    # noqa
    '<DigPoint |    EEG #26 : (3.8, -6.4, -5.3) mm      : head frame>',  # E26 [ 3.78498391 -6.40101441 -5.26004069]    # noqa
    '<DigPoint |    EEG #27 : (0.0, 9.1, 1.3) mm        : head frame>',  # E27 [0.         9.08744089 1.33334501]       # noqa
    '<DigPoint |    EEG #28 : (0.0, 3.8, 7.9) mm        : head frame>',  # E28 [0.         3.80677022 7.89130496]       # noqa
    '<DigPoint |    EEG #29 : (-3.7, 6.6, -6.5) mm      : head frame>',  # E29 [-3.74350495  6.64920491 -6.53024307]    # noqa
    '<DigPoint |    EEG #30 : (3.7, 6.6, -6.5) mm       : head frame>',  # E30 [ 3.74350495  6.64920491 -6.53024307]    # noqa
    '<DigPoint |    EEG #31 : (-6.1, 4.5, -4.4) mm      : head frame>',  # E31 [-6.11845814  4.52387011 -4.40917443]    # noqa
    '<DigPoint |    EEG #32 : (6.1, 4.5, -4.4) mm       : head frame>',  # E32 [ 6.11845814  4.52387011 -4.40917443]    # noqa
]


def test_setting_hydrocel_montage():
    """Test set_montage using GSN-HydroCel-32."""
    from mne.io import RawArray

    montage = read_montage('GSN-HydroCel-32')
    ch_names = [name for name in montage.ch_names if name.startswith('E')]
    montage.pos /= 1e3

    raw = RawArray(
        data=np.empty([len(ch_names), 1]),
        info=create_info(ch_names=ch_names, sfreq=1, ch_types='eeg')
    ).set_montage(montage)

    # test info['chs']
    _slice = [name.startswith('E') for name in montage.ch_names]
    _slice = np.array(_slice, dtype=bool)
    EXPECTED_CHS_POS = montage.pos[_slice, :]  # Shall this be in the same units as info['dig'] ??  # noqa
    actual_pos = np.array([ch['loc'][:3] for ch in raw.info['chs']])
    assert_array_equal(actual_pos, EXPECTED_CHS_POS)

    # test info['dig']
    for actual, expected in zip([str(d) for d in raw.info['dig']],
                                EXPECTED_DIG_RPR):
        assert actual == expected


def test_dig_dev_head_t_regression():
    """Test deprecated compute_dev_head_t behavior."""
    def _read_dig_montage(
        hsp=None, hpi=None, elp=None, point_names=None, unit='auto',
        fif=None, egi=None, bvct=None, transform=True, dev_head_t=False,
    ):
        """Unfolds the `read_dig_montage` old behavior of the call below.

        montage = read_dig_montage(hsp, hpi, elp, names,
                                   transform=True, dev_head_t=False)
        """
        assert isinstance(hsp, str), 'original call hsp was string'
        assert op.splitext(hpi)[-1] == '.sqd', 'original call hpi was .sqd'
        assert isinstance(elp, str), 'original call elp was string'

        hsp = _read_dig_points(hsp, unit=unit)
        hpi = read_mrk(hpi)
        elp = _read_dig_points(elp, unit=unit)

        data = Bunch(nasion=None, lpa=None, rpa=None,
                     hsp=hsp, hpi=hpi, elp=elp, coord_frame='unknown',
                     point_names=point_names, dig_ch_pos=None)

        data = _fix_data_fiducials(data)
        data = _transform_to_head_call(data)
        with pytest.deprecated_call():
            montage = DigMontage(**data)

        return montage

    EXPECTED_DEV_HEAD_T = \
        [[-3.72201691e-02, -9.98212167e-01, -4.67667497e-02, -7.31583414e-04],
         [8.98064989e-01, -5.39382685e-02, 4.36543170e-01, 1.60134431e-02],
         [-4.38285221e-01, -2.57513699e-02, 8.98466990e-01, 6.13035748e-02],
         [0.00000000e+00, 0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]

    names = ['nasion', 'lpa', 'rpa', '1', '2', '3', '4', '5']
    montage = _read_dig_montage(
        hsp, hpi, elp, names, transform=True, dev_head_t=False)

    assert montage.dev_head_t is None
    with pytest.deprecated_call():
        montage.compute_dev_head_t()
    assert_allclose(montage.dev_head_t, EXPECTED_DEV_HEAD_T, atol=1e-7)


def test_digmontage_constructor_errors():
    """Test proper error messaging."""
    with pytest.raises(ValueError, match='does not match the number'):
        _ = DigMontage(ch_names=['foo', 'bar'], dig=Digitization())


def test_transform_to_head_and_compute_dev_head_t():
    """Test transform_to_head and compute_dev_head_t."""
    EXPECTED_DEV_HEAD_T = \
        [[-3.72201691e-02, -9.98212167e-01, -4.67667497e-02, -7.31583414e-04],
         [8.98064989e-01, -5.39382685e-02, 4.36543170e-01, 1.60134431e-02],
         [-4.38285221e-01, -2.57513699e-02, 8.98466990e-01, 6.13035748e-02],
         [0.00000000e+00, 0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]

    EXPECTED_FID_IN_POLHEMUS = {
        'nasion': np.array([0.001393, 0.0131613, -0.0046967]),
        'lpa': np.array([-0.0624997, -0.0737271, 0.07996]),
        'rpa': np.array([-0.0748957, 0.0873785, 0.0811943]),
    }

    EXPECTED_FID_IN_HEAD = {
        'nasion': np.array([-8.94466792e-18, 1.10559624e-01, -3.85185989e-34]),
        'lpa': np.array([-8.10816716e-02, 6.56321671e-18, 0]),
        'rpa': np.array([8.05048781e-02, -6.47441364e-18, 0]),
    }

    hpi_dev = np.array(
        [[ 2.13951493e-02,  8.47444056e-02, -5.65431188e-02],  # noqa
         [ 2.10299433e-02, -8.03141101e-02, -6.34420259e-02],  # noqa
         [ 1.05916829e-01,  8.18485672e-05,  1.19928083e-02],  # noqa
         [ 9.26595105e-02,  4.64804385e-02,  8.45141253e-03],  # noqa
         [ 9.42554419e-02, -4.35206589e-02,  8.78999363e-03]]  # noqa
    )

    hpi_polhemus = np.array(
        [[-0.0595004, -0.0704836,  0.075893 ],  # noqa
         [-0.0646373,  0.0838228,  0.0762123],  # noqa
         [-0.0135035,  0.0072522, -0.0268405],  # noqa
         [-0.0202967, -0.0351498, -0.0129305],  # noqa
         [-0.0277519,  0.0452628, -0.0222407]]  # noqa
    )

    montage_polhemus = make_dig_montage(
        **EXPECTED_FID_IN_POLHEMUS, hpi=hpi_polhemus, coord_frame='unknown'
    )

    montage_meg = make_dig_montage(hpi=hpi_dev, coord_frame='meg')

    # Test regular worflow to get dev_head_t
    montage = montage_polhemus + montage_meg
    fids, _ = _get_fid_coords(montage.dig)
    for kk in fids:
        assert_allclose(fids[kk], EXPECTED_FID_IN_POLHEMUS[kk], atol=1e-5)

    with pytest.raises(ValueError, match='set to head coordinate system'):
        _ = compute_dev_head_t(montage)

    montage = transform_to_head(montage)

    fids, _ = _get_fid_coords(montage.dig)
    for kk in fids:
        assert_allclose(fids[kk], EXPECTED_FID_IN_HEAD[kk], atol=1e-5)

    dev_head_t = compute_dev_head_t(montage)
    assert_allclose(dev_head_t['trans'], EXPECTED_DEV_HEAD_T, atol=1e-7)

    # Test errors when number of HPI points do not match
    EXPECTED_ERR_MSG = 'Device-to-Head .*Got 0 .*device and 5 points in head'
    with pytest.raises(ValueError, match=EXPECTED_ERR_MSG):
        _ = compute_dev_head_t(transform_to_head(montage_polhemus))

    EXPECTED_ERR_MSG = 'Device-to-Head .*Got 5 .*device and 0 points in head'
    with pytest.raises(ValueError, match=EXPECTED_ERR_MSG):
        _ = compute_dev_head_t(transform_to_head(
            montage_meg + make_dig_montage(**EXPECTED_FID_IN_POLHEMUS)
        ))

    EXPECTED_ERR_MSG = 'Device-to-Head .*Got 3 .*device and 5 points in head'
    with pytest.raises(ValueError, match=EXPECTED_ERR_MSG):
        _ = compute_dev_head_t(transform_to_head(
            DigMontage(dig=_format_dig_points(montage_meg.dig[:3])) +
            montage_polhemus
        ))


run_tests_if_main()
