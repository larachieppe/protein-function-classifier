"""Estimator bounds, sampling, PRF and two-point geometry."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prebench import estimator as est
from prebench import twopoint as tp

C = 1540.0


def test_crlb_improves_with_bandwidth():
    a = est.crlb_delay_std(2e-6, 4.0e6, 6.0e6, 0.8, 2.0)
    b = est.crlb_delay_std(2e-6, 2.5e6, 7.5e6, 0.8, 2.0)
    assert b < a


def test_crlb_degrades_with_decorrelation():
    good = est.crlb_delay_std(2e-6, 3.5e6, 6.5e6, 0.9, 2.0)
    bad = est.crlb_delay_std(2e-6, 3.5e6, 6.5e6, 0.3, 2.0)
    assert bad > 2 * good


def test_precision_budget_is_met_at_the_frozen_threshold_not_at_the_floor():
    """A real constraint linking the two thresholds.

    At the frozen +6 dB detection threshold the position budget has ample margin. At the
    inherited -10 dB estimator floor it does not: the estimator still tracks, but not to
    the declared accuracy. That gap is exactly why the claim's detection threshold must
    sit above the estimator floor.
    """
    at_claim = est.crlb_delay_std(2e-6, 3.5e6, 6.5e6, 0.6, est.snr_amp_from_fbr_db(6.0))
    at_floor = est.crlb_delay_std(2e-6, 3.5e6, 6.5e6, 0.6, est.snr_amp_from_fbr_db(-10.0))
    assert float(est.delay_to_displacement(at_claim, C)) * 1e6 < 150.0
    assert float(est.delay_to_displacement(at_floor, C)) * 1e6 > 150.0


def test_precision_floor_sits_above_the_estimator_floor():
    fbr = est.min_fbr_for_precision(150e-6, C, 2e-6, 3.5e6, 6.5e6, 0.6)
    assert -10.0 < fbr < 6.0, fbr


def test_prf_window_closes_for_fast_deep_features():
    r = est.prf_feasible(0.080, 0.8, 5e6, C, 1.5e-3, 10, 0.05, phase_domain=True)
    assert not r["feasible"]
    r2 = est.prf_feasible(0.080, 0.8, 5e6, C, 1.5e-3, 10, 0.05, phase_domain=False)
    assert r2["feasible"], "window-domain tracking should still have a window"


def test_prf_range_bound_is_physical():
    assert est.prf_max_range(0.08, C, guard=1.0) == pytest.approx(C / 0.16, rel=1e-9)


def test_subsample_bias_falls_with_oversampling():
    spc = np.array([3.0, 6.0, 12.0])
    r = est.subsample_bias_experiment(5e6, 0.6, spc)
    e = r["peak_abs_error_samples"]
    assert e[0] > e[1] > e[2]


def test_undersampling_is_catastrophic():
    r = est.subsample_bias_experiment(5e6, 0.6, np.array([2.5]))
    um = est.bias_to_displacement_m(r["peak_abs_error_samples"], np.array([12.5e6]), C) * 1e6
    assert um[0] > 50.0, "2.5 samples/cycle aliases the top of the band"


def test_averaging_gain_is_ten_log_n():
    assert est.averaging_gain_db(100) == pytest.approx(20.0, abs=1e-9)


def test_enob_requirement_rises_without_averaging():
    moving = est.required_enob(73.0, 50e6, 3e6, n_avg=1)
    static = est.required_enob(73.0, 50e6, 3e6, n_avg=64)
    assert moving > static + 2.5


def test_two_point_feasibility_is_speed_independent():
    """A workable separation exists whenever lifetime > k * sigma_onset, whatever v."""
    sigma, life = 0.010, np.full(500, 0.200)
    for v in (0.02, 0.1, 0.5):
        r = tp.feasible(np.full(500, v), sigma, life, 257e-6, 0.94e-3, np.full(500, 0.065))
        assert r["feasible_fraction"] == 1.0, v


def test_two_point_infeasible_when_lifetime_too_short():
    r = tp.feasible(np.full(200, 0.1), 0.020, np.full(200, 0.010), 257e-6, 0.94e-3,
                    np.full(200, 0.065))
    assert r["feasible_fraction"] == 0.0


def test_separation_scales_linearly_with_speed():
    a = tp.separation_for_direction_error(0.1, 0.010, 0.01)
    b = tp.separation_for_direction_error(0.2, 0.010, 0.01)
    assert b == pytest.approx(2 * a, rel=1e-6)


def test_direction_confusion_falls_with_separation():
    v = np.array([0.1])
    near = float(np.atleast_1d(tp.direction_confusion_probability(v, 0.002, 0.010))[0])
    far = float(np.atleast_1d(tp.direction_confusion_probability(v, 0.040, 0.010))[0])
    assert near > 0.05 and far < 1e-3


def test_acoustic_minimum_separation_is_respected():
    lo = tp.min_separation_acoustic(257e-6, 0.94e-3)
    assert lo >= 2 * 0.94e-3
