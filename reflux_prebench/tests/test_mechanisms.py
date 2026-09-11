"""Mechanisms must stay separate, and each must make a falsifiable null prediction."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prebench import acoustics as ac
from prebench import literature as lit
from prebench import requirements as req
from prebench.mechanisms import ALL, BY_KEY, composite_interval_db
from prebench.scenarios import Scenario
from prebench.uncertain import Status


def scen(**kw):
    base = dict(route="distal_uvj", background="favourable", f0_hz=5e6, frac_bw=0.6,
                dsg=0.016, aperture_m=13.8e-3, n=4000, seed=1)
    base.update(kw)
    return Scenario(**base)


def test_every_mechanism_declares_its_falsifier_and_limits():
    for m in ALL:
        assert m.null_prediction.strip()
        assert m.falsifier.strip()
        assert m.closes_when.strip()
        assert m.does_not_close.strip()
        assert m.controls


def test_mechanisms_are_not_summed():
    """No code path adds two mechanisms into a single 'reflux signal'."""
    src = (ROOT / "prebench" / "mechanisms.py").read_text()
    assert "composite_interval_db" in src
    # M6 is the only place two mechanisms meet, and it returns an interval
    lo, hi = composite_interval_db(np.array([-30.0]), np.array([-36.0]))
    assert lo[0] < -30.0 < hi[0], "composite must bracket, not replace, its components"


def test_composite_destructive_corner_is_weaker_than_either_component():
    lo, hi = composite_interval_db(np.array([-30.0]), np.array([-31.0]))
    assert lo[0] < -40.0, "near-equal components can almost cancel"


def test_matched_fluids_produce_no_gradient_signal():
    """The declared null for M2: dSG = 0 must give nothing."""
    cond = scen(dsg=0.0).draw()
    out = BY_KEY["M2"].evaluate(cond)
    assert np.all(out.intrinsic_db < -250.0)


def test_gradient_scales_quadratically_with_contrast():
    """R_I ~ (dZ/2Z)^2: an 8x contrast step is 18 dB, before profile effects."""
    a = BY_KEY["M2"].evaluate(scen(dsg=0.002).draw()).intrinsic_db
    b = BY_KEY["M2"].evaluate(scen(dsg=0.016).draw()).intrinsic_db
    assert float(np.median(b - a)) == pytest.approx(20 * np.log10(8), abs=0.5)


def test_volume_scatter_scales_linearly_with_bsc():
    r = ac.volume_scatter_ratio(np.array([1e-6, 1e-5]), 2.57e-4, 0.12)
    assert float(r[1] / r[0]) == pytest.approx(10.0, rel=1e-9)


def test_wall_motion_has_the_strongest_echo():
    """M5 is the strongest and least specific: the ranking must hold."""
    cond = scen().draw()
    med = {m.key: float(np.median(req.clamp(m.evaluate(cond).intrinsic_db))) for m in ALL}
    assert med["M5"] == max(med.values())


def test_native_backscatter_is_the_weakest_branch():
    cond = scen().draw()
    m1 = float(np.median(req.clamp(BY_KEY["M1"].evaluate(cond).intrinsic_db)))
    m4 = float(np.median(req.clamp(BY_KEY["M4"].evaluate(cond).intrinsic_db)))
    assert m1 < m4


def test_required_urine_backscatter_exceeds_blood():
    """The headline M1 result: urine must out-scatter blood for VFI to survive."""
    cond = scen().draw()
    need = float(np.median(req.required_bsc(cond, 6.0)))
    assert need > lit.BSC_BLOOD.hi, (need, lit.BSC_BLOOD.hi)


def test_deeper_is_worse_by_attenuation_alone():
    shallow = BY_KEY["M4"].evaluate(scen(route="distal_uvj").draw())
    deep = BY_KEY["M4"].evaluate(scen(route="mid").draw())
    assert float(np.median(deep.propagated_db)) < float(np.median(shallow.propagated_db))


def test_worse_background_reduces_tolerable_capture_loss_by_exactly_10_db():
    a = BY_KEY["M4"].evaluate(scen(background="favourable").draw())
    b = BY_KEY["M4"].evaluate(scen(background="middle").draw())
    assert float(np.median(a.tolerable_capture_db - b.tolerable_capture_db)) == \
        pytest.approx(10.0, abs=0.01)


def test_clutter_suppression_helps_by_exactly_its_value():
    a = BY_KEY["M1"].evaluate(scen(clutter_suppression_db=0.0).draw())
    b = BY_KEY["M1"].evaluate(scen(clutter_suppression_db=10.0).draw())
    assert float(np.median(b.fbr_db - a.fbr_db)) == pytest.approx(10.0, abs=0.01)


def test_infeasible_requirements_are_reported_as_nan_not_clipped():
    cond = scen().draw()
    w = req.max_edge_width(cond, 6.0, 0.01)
    assert np.isnan(w).any(), "an impossible requirement must not be reported as a width"


def test_nothing_is_measured_yet():
    assert lit.ledger().by_status(Status.MEASURED) == []
