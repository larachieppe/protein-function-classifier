"""Render the experimental specification.

The output of this model is a specification for an experiment.  It is not evidence of
clinical sensitivity, and the document says so in its own header rather than relying on
the reader to remember it.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from typing import Any

import numpy as np

from . import acoustics as ac
from . import acquisition as acq
from . import estimator as est
from . import literature as lit
from . import requirements as req
from . import twopoint as tp
from .claim import FrozenClaim
from .closure import build as build_closure, ordering
from .mechanisms import ALL, BY_KEY
from .scenarios import Scenario
from .uncertain import Status

C = 1540.0


def _p(a: np.ndarray, q: float) -> float:
    return float(np.percentile(np.asarray(a, dtype=float), q))


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(header: list[str], rows: list[list[str]]) -> str:
    out = [_row(header), _row(["---"] * len(header))]
    out += [_row(r) for r in rows]
    return "\n".join(out)


# ---------------------------------------------------------------------------

def compute(claim: FrozenClaim, n: int = 30000, seed: int = 20260910) -> dict[str, Any]:
    """Run every analysis and return one results dictionary."""
    thr = float(claim.threshold("detection", "fbr_min_db"))
    floor = float(claim.threshold("detection", "estimator_floor_db"))
    snr_min = float(claim.threshold("detection", "snr_vs_noise_min_db"))
    out: dict[str, Any] = {"threshold_db": thr, "estimator_floor_db": floor}

    # -- link budget per mechanism, per background ---------------------------
    budget: dict[str, dict[str, Any]] = {}
    for m in ALL:
        per_bg = {}
        for bg in ("favourable", "middle", "worst"):
            sc = Scenario(route="distal_uvj", background=bg, f0_hz=5e6, frac_bw=0.6,
                          dsg=lit.DSG_MAX.nom, aperture_m=lit.ELEMENT_DIAMETER.nom,
                          n=n, seed=seed)
            cond = sc.draw()
            res = m.evaluate(cond, thr)
            f = req.clamp(res.fbr_db)
            per_bg[bg] = {
                "fbr_p10": _p(f, 10), "fbr_p50": _p(f, 50), "fbr_p90": _p(f, 90),
                "detect_fraction": req.detect_fraction(res.fbr_db, thr),
                "tol_capture_p50": _p(req.clamp(res.tolerable_capture_db), 50),
                "tol_capture_p90": _p(req.clamp(res.tolerable_capture_db), 90),
            }
        budget[m.key] = per_bg
    out["link_budget"] = budget

    # -- inherited-budget reconciliation -------------------------------------
    bgs = ac.recover_inherited_backgrounds()
    out["inherited"] = {
        "recovered_backgrounds_db": list(bgs),
        "recovered_dc_drho": ac.recover_inherited_dc_drho(),
        "table10_reproduction": _reproduce_table10(),
    }

    # -- attenuation correction to the inherited sharp-fraction requirement ---
    sc_fav = Scenario(route="distal_uvj", background="favourable", f0_hz=5e6, frac_bw=0.6,
                      dsg=lit.DSG_MAX.nom, aperture_m=lit.ELEMENT_DIAMETER.nom, n=n, seed=seed)
    cond_fav = sc_fav.draw()
    fG = req.required_fG(cond_fav, thr)
    cond_noatt = sc_fav.draw()
    cond_noatt.alpha = np.zeros_like(cond_noatt.alpha)
    fG_noatt = req.required_fG(cond_noatt, thr)
    # Like-for-like comparison with the inherited figures, which used the -10 dB
    # estimator floor and omitted the propagation path entirely.
    fG_inherited = req.required_fG(cond_noatt, floor)

    def _edge(f_sharp, shape="tanh", threshold=thr):
        w = req.max_edge_width(cond_fav, threshold, f_sharp, shape=shape) * 1e6
        finite = w[np.isfinite(w)]
        frac_impossible = 1.0 - len(finite) / len(w)
        if len(finite) == 0:
            return {"impossible_fraction": 1.0, "p10": None, "p50": None, "p90": None}
        return {"impossible_fraction": frac_impossible,
                "p10": _p(finite, 10), "p50": _p(finite, 50), "p90": _p(finite, 90)}

    out["m2_targets"] = {
        "required_fG_p10": _p(fG, 10), "required_fG_p50": _p(fG, 50), "required_fG_p90": _p(fG, 90),
        "required_fG_no_attenuation_p50": _p(fG_noatt, 50),
        "required_fG_inherited_conditions_p50": _p(fG_inherited, 50),
        "infeasible_fraction": req.fG_infeasible_fraction(cond_fav, thr),
        "attenuation_penalty_factor": _p(fG, 50) / max(_p(fG_noatt, 50), 1e-12),
        "edge_f1": _edge(1.0),
        "edge_f01": _edge(0.1),
        "edge_f1_at_inherited_threshold": _edge(1.0, threshold=floor),
        "profile_shape_sensitivity_um": {
            sh: _edge(1.0, shape=sh)["p50"] for sh in ("tanh", "linear", "gaussian")
        },
    }

    # -- M1 targets -----------------------------------------------------------
    m1 = {}
    for cs in (0.0, 5.0, 10.0, 20.0):
        sc = Scenario(route="distal_uvj", background="favourable", f0_hz=5e6, frac_bw=0.6,
                      dsg=lit.DSG_MAX.nom, aperture_m=lit.ELEMENT_DIAMETER.nom,
                      clutter_suppression_db=cs, n=n, seed=seed)
        c2 = sc.draw()
        r = req.required_bsc(c2, thr) / 10 ** (cs / 10.0)
        m1[f"clutter_{int(cs)}dB"] = {"p10": _p(r, 10), "p50": _p(r, 50), "p90": _p(r, 90)}
    out["m1_targets"] = {
        "required_bsc": m1,
        "blood_reference": [lit.BSC_BLOOD.lo, lit.BSC_BLOOD.hi],
        "instrument_floor_bsc_p50": _p(req.bsc_noise_floor(cond_fav, -100.0), 50),
    }

    # -- M4 target ------------------------------------------------------------
    out["m4_targets"] = {
        "cancellation_scale_um": _p(req.min_lumen_opening_for_contrast(cond_fav) * 1e6, 50),
        "quarter_wave_um": C / 5e6 / 4 * 1e6,
        "collapsed_film_bracket_um": [lit.LUMEN_COLLAPSED.lo * 1e6, lit.LUMEN_COLLAPSED.hi * 1e6],
    }

    # -- M5 target ------------------------------------------------------------
    rng = np.random.default_rng(seed)
    resp = lit.RESP_EXCURSION.sample(rng, n)
    out["m5_targets"] = {
        f"rejection_db_for_{int(d*1e6)}um_signal": [
            _p(req.motion_rejection_required(d, resp), q) for q in (10, 50, 90)]
        for d in (50e-6, 200e-6, 500e-6)
    }

    # -- frequency optimisation ----------------------------------------------
    # 15 MHz and above is excluded by attenuation alone (>50 dB two-way at 35 mm).
    f_grid = np.array([1e6, 2e6, 3e6, 4e6, 5e6, 7e6, 10e6])
    freq = {}
    for m in ALL:
        def factory(f0, _m=m):
            return Scenario(route="distal_uvj", background="favourable", f0_hz=f0,
                            frac_bw=0.6, dsg=lit.DSG_MAX.nom,
                            aperture_m=lit.ELEMENT_DIAMETER.nom, n=8000, seed=seed).draw()
        freq[m.key] = req.sweep_frequency(m, factory, f_grid, thr)
    # A frequency is only usable if its axial resolution can still separate the feature
    # from the nearest wall echo. Without this constraint the sweep trivially prefers the
    # lowest frequency on the grid, because attenuation is the only term that sees f.
    wall_sep_req = 0.5e-3
    frac_bw = 0.6
    f0_min_resolution = C / (2.0 * wall_sep_req * frac_bw)
    permitted = f_grid >= f0_min_resolution
    med = {k: np.asarray(v["median_fbr_db"]) for k, v in freq.items()}
    best = {}
    penalty = {}
    for k, v in med.items():
        masked = np.where(permitted, v, -np.inf)
        best[k] = float(f_grid[int(np.argmax(masked))])
        idx = np.where(permitted)[0]
        penalty[k] = float(v[idx[0]] - v[idx[-1]])
    out["frequency"] = {
        "f_hz": f_grid.tolist(),
        "permitted": permitted.tolist(),
        "f0_min_resolution_hz": f0_min_resolution,
        "wall_separation_req_m": wall_sep_req,
        "median_fbr_db": {k: [float(x) for x in v] for k, v in med.items()},
        "detect_fraction": {k: [float(x) for x in v["detect_fraction"]] for k, v in freq.items()},
        "best_f_hz": best,
        "penalty_across_band_db": penalty,
    }

    # -- bandwidth ------------------------------------------------------------
    bw = acq.bandwidth_requirements(C, lumen_open_min=lit.LUMEN_OPEN.lo,
                                    wall_sep_min=0.5e-3, edge_target=100e-6,
                                    f_lo=2.0e6, f_hi=7.0e6)
    bw["recommended_f_lo_hz"] = 2.0e6
    bw["recommended_f_hi_hz"] = 7.0e6
    bw["recommended_f0_hz"] = 4.0e6
    bw["recommended_bw_hz"] = 5.0e6
    bw["recommended_frac_bw"] = 5.0 / 4.0
    # With a broadband element the resolution floor on f0 relaxes, because resolution is
    # set by absolute bandwidth, not by centre frequency.
    bw["f0_floor_at_recommended_bw_hz"] = C / (2.0 * 0.5e-3 * bw["recommended_frac_bw"])
    bw["frac_bw_for_position_target"] = acq.bandwidth_for_position_error(
        float(claim.threshold("accuracy", "displacement_precision_max_m")),
        C, 5e6, 2e-6, 0.5, floor)
    out["bandwidth"] = bw

    # -- sampling rate --------------------------------------------------------
    spc = np.array([2.5, 3.0, 4.0, 6.0, 8.0, 10.0, 16.0, 20.0])
    bias = est.subsample_bias_experiment(5e6, 0.6, spc)
    bias_um = est.bias_to_displacement_m(bias["peak_abs_error_samples"], spc * 5e6, C) * 1e6
    # Criterion: interpolation bias must be under 10% of the frozen per-estimate budget.
    budget_um = float(claim.threshold("accuracy", "displacement_precision_max_m")) * 1e6
    ok = np.where(bias_um <= 0.1 * budget_um)[0]
    chosen_spc = float(spc[ok[0]]) if len(ok) else float(spc[-1])
    nyquist_fs = 2.5 * 7.5e6
    out["sampling"] = {
        "samples_per_cycle": spc.tolist(),
        "peak_abs_error_samples": bias["peak_abs_error_samples"].tolist(),
        "peak_bias_um": bias_um.tolist(),
        "budget_um": budget_um,
        "criterion_um": 0.1 * budget_um,
        "chosen_samples_per_cycle": chosen_spc,
        "bias_limited_fs_hz": chosen_spc * 5e6,
        "nyquist_limited_fs_hz": nyquist_fs,
        "required_fs_hz": est.required_fs(7.5e6, chosen_spc, 5e6),
        "binding": "Nyquist over the 2.5-7.5 MHz band" if nyquist_fs >= chosen_spc * 5e6
                   else "interpolation bias",
    }

    # -- PRF ------------------------------------------------------------------
    prf_rows = []
    for v in (0.02, 0.1, 0.3, 0.5, 0.8):
        for d in (0.035, 0.060, 0.080):
            r = est.prf_feasible(d, v, 5e6, C, window_len_m=1.5e-3,
                                 n_frames=int(claim.threshold("tracking", "min_consecutive_estimates")),
                                 lifetime_s=lit.T_FEATURE_LIFE.lo, phase_domain=True)
            r2 = est.prf_feasible(d, v, 5e6, C, window_len_m=1.5e-3,
                                  n_frames=int(claim.threshold("tracking", "min_consecutive_estimates")),
                                  lifetime_s=lit.T_FEATURE_LIFE.lo, phase_domain=False)
            prf_rows.append({"v": v, "depth": d, "phase": r, "window": r2})
    out["prf"] = prf_rows

    # -- depth coverage -------------------------------------------------------
    d_lo = min(lit.DEPTH_DISTAL.lo, lit.DEPTH_PROXIMAL.lo, lit.DEPTH_MID.lo)
    d_hi = max(lit.DEPTH_DISTAL.hi, lit.DEPTH_PROXIMAL.hi, lit.DEPTH_MID.hi)
    out["depth"] = {
        "required_lo_m": d_lo, "required_hi_m": d_hi,
        "provisional_element_coverage_m": list(acq.depth_coverage(
            lit.ELEMENT_FOCUS.nom, 3.0, 5e6, C)),
        "tiles_f3": acq.elements_needed(d_lo, d_hi, 3.0, 5e6, C),
        "tiles_f2": acq.elements_needed(d_lo, d_hi, 2.0, 5e6, C),
        "attenuation_db_at_hi": float(ac.attenuation_db(d_hi, 5e6, lit.ALPHA_TISSUE.nom)),
        "attenuation_db_at_lo": float(ac.attenuation_db(d_lo, 5e6, lit.ALPHA_TISSUE.nom)),
    }

    # -- angle and aperture ---------------------------------------------------
    out["angle"] = {
        "wide_reflector_5mm": acq.angular_sweep(5e6, C, 5e-3),
        "narrow_reflector_2mm": acq.angular_sweep(5e6, C, 2e-3),
    }
    ap = np.array([4e-3, 6e-3, 9e-3, 13.8e-3, 19e-3])
    out["aperture"] = acq.aperture_discriminator(ap, 0.035)
    out["aperture"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                       for k, v in out["aperture"].items()}

    # -- two-point separation -------------------------------------------------
    rng = np.random.default_rng(seed + 1)
    v_s = lit.V_FEATURE.sample(rng, n)
    life_s = lit.T_FEATURE_LIFE.sample(rng, n)
    seg = lit.URETER_LENGTH.sample(rng, n) * 0.5
    axial = float(ac.axial_resolution(C, 3e6))
    beam = float(ac.lateral_beamwidth(5e6, C, 3.0))
    two = {}
    for sig in (0.002, 0.010, 0.020):
        f = tp.feasible(v_s, sig, life_s, axial, beam, seg)
        rec = f["recommended_m"][~np.isnan(f["recommended_m"])]
        two[f"sigma_onset_{int(sig*1000)}ms"] = {
            "feasible_fraction": f["feasible_fraction"],
            "recommended_mm": [float(np.percentile(rec, q) * 1000) for q in (10, 50, 90)],
            "lifetime_criterion_ms": f["lifetime_criterion_s"] * 1000,
        }
    two["fixed_separation_for_1pct_direction_error_mm"] = {
        f"v_{int(v*1000)}mm_s": tp.separation_for_direction_error(v, 0.010, 0.01) * 1000
        for v in (0.02, 0.1, 0.5, 0.8)
    }
    two["acoustic_minimum_mm"] = tp.min_separation_acoustic(axial, beam) * 1000
    out["two_point"] = two

    # -- receiver -------------------------------------------------------------
    # The weakest level the instrument must resolve is the BACKGROUND, not the weakest
    # conceivable mechanism: feature-to-background is a ratio, so the denominator has to be
    # measured with margin before any numerator means anything. Sizing the digitiser
    # against the most hopeless corner of the most hopeless mechanism would demand an
    # impossible converter to characterise a signal nobody claims exists.
    background = float(lit.BG_FAVOURABLE.nom)
    weakest = background - snr_min
    strongest = float(ac.db(ac.reflected_intensity(0.10)))  # strong wall / fixture echo
    dr = acq.dynamic_range_requirement(strongest, weakest)
    fs = out["sampling"]["required_fs_hz"]
    out["receiver"] = acq.receiver_spec(dr, fs, 3e6, n_avg_static=64)
    out["receiver"]["strongest_in_gate_db"] = strongest
    out["receiver"]["weakest_required_db"] = weakest
    out["receiver"]["background_db"] = background
    out["receiver"]["snr_margin_db"] = snr_min

    # -- precision margin -----------------------------------------------------
    prec = {}
    for fbr, rho, label in ((floor, 0.6, "at the estimator floor, heavy decorrelation"),
                            (0.0, 0.8, "at 0 dB FBR, good correlation"),
                            (thr, 0.8, "at the frozen threshold, good correlation"),
                            (thr, 0.3, "at the frozen threshold, severe decorrelation")):
        st = est.crlb_delay_std(2e-6, 3.5e6, 6.5e6, rho, est.snr_amp_from_fbr_db(fbr))
        prec[f"FBR {fbr:+.0f} dB, rho {rho} — {label}"] = float(
            est.delay_to_displacement(st, C) * 1e6)
    out["precision_um"] = prec
    budget_m = float(claim.threshold("accuracy", "displacement_precision_max_m"))
    out["precision_budget_um"] = budget_m * 1e6
    out["precision_floor_fbr_db"] = {
        f"rho_{rho}": est.min_fbr_for_precision(budget_m, C, 2e-6, 3.5e6, 6.5e6, rho)
        for rho in (0.9, 0.6, 0.3)
    }

    # -- fluid property ranges to prepare -------------------------------------
    out["fluids"] = _fluid_plan()

    # -- closure --------------------------------------------------------------
    scen = {m.key: Scenario(route="distal_uvj", background="favourable", f0_hz=5e6,
                            frac_bw=0.6, dsg=lit.DSG_MAX.nom,
                            aperture_m=lit.ELEMENT_DIAMETER.nom, n=n, seed=seed)
            for m in ALL}
    rows = build_closure(claim, scen)
    out["closure"] = [r.as_dict() for r in rows]
    out["screening_order"] = ordering(rows)
    return out


def _reproduce_table10() -> list[dict[str, Any]]:
    bgs = ac.recover_inherited_backgrounds()
    dcdrho = ac.recover_inherited_dc_drho()
    ib = ac.InheritedBudget()
    rows = []
    for label, rp, published in (
        ("empty-fill leading edge", ib.r_p_empty_fill, ib.empty_fill),
        ("dSG = 0.016 fluid-fluid", float(ac.r_p_from_dsg(0.016, dcdrho, 1010.0, 1540.0)), ib.dsg_016),
        ("dSG = 0.002 fluid-fluid", float(ac.r_p_from_dsg(0.002, dcdrho, 1010.0, 1540.0)), ib.dsg_002),
    ):
        sig = float(ac.db(ac.reflected_intensity(rp)))
        calc = [float(ac.tolerable_capture_loss(sig, b)) for b in bgs]
        rows.append({"row": label, "r_p": rp, "signal_db": sig,
                     "model": calc, "published": list(published),
                     "max_abs_error_db": max(abs(a - b) for a, b in zip(calc, published))})
    return rows


def _fluid_plan() -> dict[str, Any]:
    steps = [0.002, 0.004, 0.006, 0.008, 0.010, 0.013, 0.016]
    rows = []
    for dsg in steps:
        lo = float(ac.r_p_from_dsg(dsg, lit.DC_DRHO.lo, 1010.0, 1540.0))
        hi = float(ac.r_p_from_dsg(dsg, lit.DC_DRHO.hi, 1010.0, 1540.0))
        rows.append({
            "dsg": dsg,
            "delta_rho_kg_m3": dsg * 1000.0,
            "r_p_range": [lo, hi],
            "R_I_db_range": [float(ac.db(lo**2)), float(ac.db(hi**2))],
        })
    return {
        "ladder": rows,
        "note": ("Every preparation must have rho and c measured independently at the "
                 "acquisition temperature. The dc/drho bracket alone spreads the reflected "
                 "intensity by about 5 dB at every step, which is why specific gravity "
                 "cannot be the calibration variable."),
        "spread_db": float(ac.db((lit.DC_DRHO.hi * 1010 / 1540 + 1) ** 2)
                           - ac.db((lit.DC_DRHO.lo * 1010 / 1540 + 1) ** 2)),
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render(claim: FrozenClaim, r: dict[str, Any]) -> str:
    L: list[str] = []
    add = L.append
    thr = r["threshold_db"]

    add("# Pre-bench experimental specification")
    add("")
    add("**Programme:** ultrasound directional reflux detection — pulse-echo "
        "reflux-feature tracking  ")
    add(f"**Generated:** {_dt.date.today().isoformat()}  ")
    add(f"**Against frozen claim:** `{claim.raw.get('version')}` "
        f"hash `{claim.short_hash}` — status *{claim.raw.get('status')}*")
    add("")
    add("> **What this document is.** The output of a literature-informed model whose only "
        "job is to design an experiment. It converts published ranges and explicit "
        "unknowns into instrument requirements, bench sweeps, and stop thresholds.")
    add(">")
    add("> **What it is not.** It is not evidence of clinical sensitivity, of a native "
        "reflux signal, of a transcutaneous window in a child, or of any device "
        "performance. Every mechanism below is modelled separately and none of the "
        "numbers may be combined into a single \"reflux signal\".")
    add("")

    # --- provenance
    reg = lit.ledger()
    add("## 0. Provenance of every input")
    add("")
    counts = {s.value: len(reg.by_status(s)) for s in Status}
    add(_table(["Status", "Count", "Meaning"], [
        ["MEASURED", str(counts["MEASURED"]), "measured on this programme's bench"],
        ["PUBLISHED", str(counts["PUBLISHED"]), "external literature"],
        ["DERIVED", str(counts["DERIVED"]), "computed from other entries"],
        ["SIMULATED", str(counts["SIMULATED"]), "this programme's own model output"],
        ["ASSUMED", str(counts["ASSUMED"]), "modelling choice, no evidential support"],
        ["UNMEASURED", str(counts["UNMEASURED"]), "genuinely unknown, bracketed wide"],
    ]))
    add("")
    add(f"**Nothing is MEASURED yet.** That is the reason for the bench. "
        f"The widest brackets, in decades of ignorance:")
    add("")
    add(_table(["Quantity", "Bracket", "Decades", "Why it is load-bearing"],
               [[q.name, q.fmt(), f"{q.decades:.1f}", q.note.split(".")[0]]
                for q in reg.unmeasured_load_bearing()[:6]]))
    add("")

    # --- claim cost
    add("## 1. What the frozen claim costs to test")
    add("")
    tc = claim.trial_counts()
    add(_table(["Threshold", "Value", "Acquisitions needed (0 failures)", "If 1 failure"], [
        ["Candidate false alarm", f"<= {tc['candidate_false_alarm']['threshold']:.0%}",
         str(tc["candidate_false_alarm"]["n_trials_zero_failures"]),
         str(tc["candidate_false_alarm"]["n_trials_one_failure"])],
        ["Retrograde direction false alarm", f"<= {tc['direction_false_alarm']['threshold']:.0%}",
         str(tc["direction_false_alarm"]["n_trials_zero_failures"]),
         str(tc["direction_false_alarm"]["n_trials_one_failure"])],
        ["Correct-direction rate",
         f">= {tc['correct_direction']['threshold']:.0%} "
         f"(lower bound {tc['correct_direction']['lower_bound_required']:.0%})",
         str(tc["correct_direction"]["n_trials"]), "-"],
    ]))
    add("")
    add("These counts are the claim. A false-alarm ceiling quoted without the trials that "
        "could detect a violation is not a threshold.")
    add("")

    # --- inherited reconciliation
    inh = r["inherited"]
    add("## 2. Reconciliation with the inherited link budget")
    add("")
    add("The inherited tolerable-capture-loss table is reproduced exactly from first "
        "principles, which recovers the two constants it never stated:")
    add("")
    add(_table(["Row", "r_p", "Signal (dB)", "This model (fav/mid/worst)", "Published",
                "Max error"],
               [[t["row"], f"{t['r_p']:.5f}", f"{t['signal_db']:.1f}",
                 " / ".join(f"{x:.1f}" for x in t["model"]),
                 " / ".join(f"{x:.1f}" for x in t["published"]),
                 f"{t['max_abs_error_db']:.2f} dB"]
                for t in inh["table10_reproduction"]]))
    add("")
    add(f"- **Recovered background levels:** "
        f"{', '.join(f'{b:.1f} dB' for b in inh['recovered_backgrounds_db'])} "
        f"re a perfect reflector. These three numbers carried the entire inherited budget "
        f"and were never visible in it.")
    add(f"- **Recovered dc/drho:** {inh['recovered_dc_drho']:.2f} (m/s)/(kg/m^3). That is a "
        f"salt-dominated composition. Urine is urea-dominated, so the inherited budget may "
        f"be optimistic by several dB. The bench removes this constant entirely by "
        f"measuring rho and c independently.")
    m2i = r["m2_targets"]
    add(f"- **Under the inherited assumptions this model agrees.** At the inherited -10 dB "
        f"estimator floor with no propagation path, the required sharp fraction comes out "
        f"at {m2i['required_fG_inherited_conditions_p50']*100:.2f}%, against the inherited "
        f"figure of 1.1%.")
    add(f"- **Attenuation was omitted from the inherited budget.** Reinstating two-way "
        f"soft-tissue attenuation at the declared depths multiplies the required sharp "
        f"fraction by {m2i['attenuation_penalty_factor']:.0f}x. Raising the detection "
        f"threshold from the estimator floor ({r['estimator_floor_db']:+.0f} dB) to the "
        f"frozen claim ({thr:+.0f} dB) multiplies it by a further "
        f"{10**((thr - r['estimator_floor_db'])/20):.1f}x. Together they move the "
        f"requirement from {m2i['required_fG_inherited_conditions_p50']*100:.1f}% to "
        f"{m2i['required_fG_p50']*100:.0f}%.")
    add("")

    # --- link budget
    add("## 3. Per-mechanism link budget")
    add("")
    add(f"Feature-to-background ratio in dB at 5 MHz, distal route, dSG = 0.016, across the "
        f"full uncertainty space. Detection threshold from the frozen claim is "
        f"**{thr:+.0f} dB**; the inherited estimator floor is {r['estimator_floor_db']:+.0f} dB.")
    add("")
    rows = []
    for m in ALL:
        b = r["link_budget"][m.key]
        rows.append([f"{m.key} {m.name}",
                     f"{b['favourable']['fbr_p10']:.0f} / {b['favourable']['fbr_p50']:.0f} / {b['favourable']['fbr_p90']:.0f}",
                     f"{b['worst']['fbr_p50']:.0f}",
                     f"{b['favourable']['detect_fraction']:.0%}",
                     m.freq_exponent])
    add(_table(["Mechanism", "FBR fav. bg (10/50/90 pct)", "FBR worst bg (median)",
                "Clears threshold", "Frequency exponent"], rows))
    add("")
    add(f"*\"Clears threshold\" is the fraction of a deliberately flat prior over unmeasured "
        f"brackets. It is a width-of-ignorance statistic, never a sensitivity. Levels are "
        f"clamped at a {req.FLOOR_DB:.0f} dB reporting floor: an entry at that value means "
        f"\"arbitrarily far below\", not a computed level.*")
    add("")

    # --- bench targets
    add("## 4. The smallest signal the system must measure")
    add("")
    m1 = r["m1_targets"]
    add("**M1 — native distributed backscatter.** Required urine backscatter coefficient "
        "to clear threshold, as a function of how much clutter suppression is achieved:")
    add("")
    add(_table(["Clutter suppression", "Required BSC 1/(m sr), median", "vs whole blood"],
               [[k.replace("clutter_", "").replace("dB", " dB"), f"{v['p50']:.2g}",
                 f"{v['p50']/lit.BSC_BLOOD.nom:.0f}x blood"]
                for k, v in m1["required_bsc"].items()]))
    add("")
    best = min(v["p50"] for v in m1["required_bsc"].values())
    worst = max(v["p50"] for v in m1["required_bsc"].values())
    add(f"Whole blood sits at {lit.BSC_BLOOD.lo:.0e} – {lit.BSC_BLOOD.hi:.0e} 1/(m sr). "
        f"**Native urine would have to backscatter between "
        f"{best/lit.BSC_BLOOD.nom:.0f}x and {worst/lit.BSC_BLOOD.nom:.0f}x whole blood** "
        f"for the VFI branch to clear the frozen threshold — and the favourable end of "
        f"that range assumes 20 dB of clutter suppression, against the roughly 5 dB the "
        f"programme's own simulations achieved with a longer coherent ensemble. One "
        f"measurement — a gate wholly inside homogeneous flowing urine, against the "
        f"terminated-receiver record — settles it, and it needs the simplest rig in the "
        f"programme.")
    add("")
    m2 = r["m2_targets"]
    e1, e01 = m2["edge_f1"], m2["edge_f01"]
    add(f"**M2 — urine-urine gradient.** The decisive quantity is the product "
        f"`f x G(k, L_edge)` — the fraction of the impedance step carried in the leading "
        f"edge, times that edge's profile factor. At dSG = 0.016 it must exceed "
        f"**{m2['required_fG_p50']*100:.0f}%** (10th percentile "
        f"{m2['required_fG_p10']*100:.0f}%).")
    add("")
    add(f"Because f and G are both fractions, their product cannot exceed 1. **In "
        f"{m2['infeasible_fraction']:.0%} of the sampled space the requirement exceeds 1, "
        f"meaning no profile of any shape clears the threshold** — the mechanism is not "
        f"merely demanding there, it is impossible.")
    add("")
    add(_table(["Sharp fraction", "Required leading-edge width", "Fraction of space where no width works"],
               [["f = 1 (whole step in the edge)",
                 f"< {e1['p50']:.0f} um (10–90 pct {e1['p10']:.0f}–{e1['p90']:.0f})",
                 f"{e1['impossible_fraction']:.0%}"],
                ["f = 0.1",
                 "no width works" if e01["p50"] is None else f"< {e01['p50']:.0f} um",
                 f"{e01['impossible_fraction']:.0%}"]]))
    add("")
    ps = m2["profile_shape_sensitivity_um"]
    add(f"That width also depends on an *unvalidated profile shape*: "
        f"tanh {ps['tanh']:.0f} um, linear ramp {ps['linear']:.0f} um, "
        f"Gaussian {ps['gaussian']:.0f} um — a factor of "
        f"{max(ps.values())/max(min(ps.values()),1e-9):.1f}. "
        f"**The bench must measure the profile shape, not only a width.** "
        f"(For reference, lambda/4 at 5 MHz is {C/5e6/4*1e6:.0f} um.)")
    add("")
    m4 = r["m4_targets"]
    add(f"**M4 — lumen opening.** Two wall-fluid surfaces separated by h return "
        f"`2|r| sin(kh)`, so the pair cancels only below about "
        f"{m4['cancellation_scale_um']:.0f} um. The residual film in an apposed ureter is "
        f"bracketed at {m4['collapsed_film_bracket_um'][0]:.0f}–"
        f"{m4['collapsed_film_bracket_um'][1]:.0f} um, which straddles the quarter-wave "
        f"maximum at {m4['quarter_wave_um']:.0f} um. **A \"collapsed\" lumen is therefore "
        f"not acoustically silent, and the echo change on opening can be negative.** "
        f"Amplitude versus opening is non-monotonic — a direct, cheap, falsifiable "
        f"prediction the collapsible-channel rig can test on its first day.")
    add("")
    m5 = r["m5_targets"]
    add("**M5 — wall motion.** Required common-mode motion rejection before a "
        "reflux-attributable wall displacement can be claimed:")
    add("")
    add(_table(["Reflux wall displacement", "Rejection needed (10/50/90 pct)"],
               [[k.split("_")[3].replace("um", " um"),
                 " / ".join(f"{x:.0f} dB" for x in v)] for k, v in m5.items()]))
    add("")
    add("This mechanism has the strongest echo and the weakest specificity. It is the one "
        "most likely to pass a bench that has no breathing, no bladder contraction and no "
        "operator hand tremor.")
    add("")

    # --- instrument spec
    add("## 5. Derived instrument specification")
    add("")
    bw = r["bandwidth"]
    samp = r["sampling"]
    rx = r["receiver"]
    dep = r["depth"]
    add(_table(["Quantity", "Requirement", "Set by"], [
        ["Centre frequency",
         f"{bw['recommended_f0_hz']/1e6:.0f} MHz, not the inherited 5 MHz",
         "every mechanism prefers the low end of the usable band and M2 prefers it by "
         "126 dB (see 5.5); with the recommended bandwidth the resolution floor on centre "
         f"frequency falls to {bw['f0_floor_at_recommended_bw_hz']/1e6:.1f} MHz, so this is "
         "a mechanism-coverage choice, not a resolution-limited one"],
        ["-6 dB bandwidth",
         f">= {bw['separate_from_wall_hz']/1e6:.1f} MHz required; specify "
         f">= {bw['recommended_bw_hz']/1e6:.0f} MHz "
         f"({bw['recommended_frac_bw']*100:.0f}% fractional at "
         f"{bw['recommended_f0_hz']/1e6:.0f} MHz)",
         f"resolve an open lumen {bw['resolve_open_lumen_hz']/1e6:.1f} MHz; separate feature "
         f"from wall {bw['separate_from_wall_hz']/1e6:.1f} MHz; resolve a 100 um edge "
         f"{bw['resolve_leading_edge_hz']/1e6:.1f} MHz (desirable, not necessary); "
         f"mechanism discrimination needs the band ratio, not the width"],
        ["Band coverage",
         f"{bw['recommended_f_lo_hz']/1e6:.0f} – {bw['recommended_f_hi_hz']/1e6:.0f} MHz "
         f"contiguous ({bw['band_ratio']:.1f}:1 band ratio)",
         f"frequency-exponent uncertainty {bw['exponent_sigma']:.2f} over that ratio "
         f"separates specular (n=0) from diffuse (n=4) by more than 10 sigma"],
        ["Sampling rate", f">= {samp['required_fs_hz']/1e6:.1f} MS/s absolute; "
                          f"specify >= 25 MS/s, prefer 50 MS/s",
         f"Nyquist over the recommended band; interpolation bias is satisfied at "
         f"{samp['bias_limited_fs_hz']/1e6:.0f} MS/s"],
        ["ADC resolution", f">= {rx['bits_moving_feature']} bit "
                           f"(ENOB >= {rx['enob_moving_feature']:.1f})",
         "moving features cannot be coherently averaged, so instantaneous dynamic range must carry it"],
        ["Instantaneous dynamic range", f">= {rx['dynamic_range_db']:.0f} dB",
         f"strongest in-gate echo {rx['strongest_in_gate_db']:.0f} dB down to "
         f"{rx['snr_margin_db']:.0f} dB below the background level "
         f"({rx['background_db']:.0f} dB), because feature-to-background is a ratio and the "
         f"denominator must be measured with margin"],
        ["Receiver noise floor",
         f"<= {rx['weakest_required_db']:.0f} dB re a perfect reflector "
         f"(<= {rx['max_input_noise_v_rms']*1e6:.0f} uV rms if the reference echo is 1 V)",
         "calibrated on day one against a flat plate, not an absolute pressure calculation"],
        ["Time-gain compensation", "None inside the primary ratio",
         "a depth-varying gain makes feature-to-background unmeasurable"],
        ["Axial resolution", f"{ac.axial_resolution(C, 3e6)*1e6:.0f} um at 3 MHz bandwidth; "
                             f"{ac.axial_resolution(C, 5e6)*1e6:.0f} um at 5 MHz",
         "c / 2B"],
        ["Usable depth range", f"{dep['required_lo_m']*1000:.0f} – {dep['required_hi_m']*1000:.0f} mm",
         "distal, mid and proximal routes in an 18-24 month child"],
    ]))
    add("")
    cov = dep["provisional_element_coverage_m"]
    add(f"**Depth coverage is a purchasing decision, and the provisional element does not "
        f"make it.** A 42 mm focus at f/3.0 covers {cov[0]*1000:.0f}–{cov[1]*1000:.0f} mm "
        f"at -6 dB — matching the programme's own stated 3.2–5.3 cm. The required sweep is "
        f"{dep['required_lo_m']*1000:.0f}–{dep['required_hi_m']*1000:.0f} mm, which needs "
        f"**{len(dep['tiles_f3'])} fixed-focus elements at f/3.0** "
        f"(foci {', '.join(f'{t[0]*1000:.0f}' for t in dep['tiles_f3'])} mm) "
        f"or {len(dep['tiles_f2'])} at f/2.0. Two-way attenuation across that sweep ranges "
        f"from {dep['attenuation_db_at_lo']:.0f} to {dep['attenuation_db_at_hi']:.0f} dB at "
        f"5 MHz, so depth is not a second-order variable.")
    add("")

    # sampling table
    add("### 5.1 Sampling rate, measured rather than assumed")
    add("")
    add(_table(["Samples per cycle", "fs at 5 MHz", "Peak interpolation bias (samples)",
                "as displacement"],
               [[f"{sp:g}", f"{sp*5:.1f} MS/s", f"{pe:.4f}", f"{um:.3f} um"]
                for sp, pe, um in zip(samp["samples_per_cycle"],
                                      samp["peak_abs_error_samples"],
                                      samp["peak_bias_um"])]))
    add("")
    add(f"Parabolic sub-sample interpolation of a shifted Gabor pulse, run at high SNR so "
        f"the measured quantity is bias rather than noise. The criterion is 10% of the "
        f"frozen per-estimate precision budget ({samp['criterion_um']:.0f} um), which "
        f"{samp['chosen_samples_per_cycle']:g} samples/cycle already meets. "
        f"**The binding constraint is therefore {samp['binding']} "
        f"({samp['nyquist_limited_fs_hz']/1e6:.1f} MS/s), not interpolation.** "
        f"Specify >= 25 MS/s for margin; 50 MS/s buys another order of magnitude of bias "
        f"headroom for negligible cost, and 12.5 MS/s (2.5 samples/cycle) aliases the top "
        f"of the band and fails catastrophically at "
        f"{samp['peak_bias_um'][0]:.0f} um.")
    add("")

    # PRF
    add("### 5.2 Pulse-repetition frequency: where the window closes")
    add("")
    add("PRF is bounded above by range ambiguity and below by per-pulse motion and the "
        "minimum track length. Phase-domain tracking (motion < lambda/4 per pulse) is the "
        "demanding case.")
    add("")
    prf_rows = []
    for row in r["prf"]:
        ph, wd = row["phase"], row["window"]
        prf_rows.append([f"{row['v']*1000:.0f} mm/s", f"{row['depth']*1000:.0f} mm",
                         f"{ph['prf_min_hz']/1e3:.1f}", f"{ph['prf_max_range_hz']/1e3:.1f}",
                         "yes" if ph["feasible"] else "**no**",
                         "yes" if wd["feasible"] else "no"])
    add(_table(["Feature speed", "Depth", "PRF min (kHz)", "PRF max (kHz)",
                "Phase-domain feasible", "Window-domain feasible"], prf_rows))
    add("")
    infeasible = [row for row in r["prf"] if not row["phase"]["feasible"]]
    if infeasible:
        add(f"**{len(infeasible)} of {len(r['prf'])} speed/depth combinations have no "
            f"phase-domain PRF window at 5 MHz.** Where the window closes, the options are "
            f"a lower centre frequency, a restricted depth, or envelope/window-domain "
            f"tracking with its coarser precision. This must be decided before the "
            f"digitiser is configured, not after a failed run.")
    add("")

    # two point
    tpr = r["two_point"]
    add("### 5.3 Distance between the two observation points")
    add("")
    add(_table(["Onset-timing uncertainty", "Recommended separation (10/50/90 pct)",
                "Feasible fraction", "Requires feature lifetime above"],
               [[k.replace("sigma_onset_", "").replace("ms", " ms"),
                 " / ".join(f"{x:.0f}" for x in v["recommended_mm"]) + " mm",
                 f"{v['feasible_fraction']:.0%}",
                 f"{v['lifetime_criterion_ms']:.0f} ms"]
                for k, v in tpr.items() if k.startswith("sigma_onset")]))
    add("")
    add(_table(["Feature speed", "Separation for 1% timing-only wrong-direction rate"],
               [[k.replace("v_", "").replace("mm_s", " mm/s"), f"{v:.1f} mm"]
                for k, v in tpr["fixed_separation_for_1pct_direction_error_mm"].items()]))
    add("")
    add(f"The timing bound and the lifetime bound both scale with feature speed, so their "
        f"ratio does not: **a workable separation exists whenever the feature lives longer "
        f"than about three onset-timing uncertainties, independently of how fast it moves.** "
        f"Speed only decides *where* in the window to put the points — and it is unmeasured "
        f"across nearly two decades. The recommended separation therefore spans "
        f"{tpr['sigma_onset_10ms']['recommended_mm'][0]:.0f}–"
        f"{tpr['sigma_onset_10ms']['recommended_mm'][2]:.0f} mm.")
    add("")
    add(f"**Hardware consequence:** the dynamic bench needs a *settable* second observation "
        f"position on a surveyed translation stage spanning at least "
        f"{tpr['acoustic_minimum_mm']:.0f}–40 mm, not a fixed two-transducer mount. A fixed "
        f"separation chosen for fast features makes slow short-lived features "
        f"indeterminate, and vice versa.")
    add("")

    # angle / aperture
    ang = r["angle"]
    add("### 5.4 Angle and aperture sweeps")
    add("")
    add(_table(["Illuminated reflector width", "Specular lobe FWHM", "Max angular step",
                "Angles over +/-40 deg"],
               [["5 mm", f"{ang['wide_reflector_5mm']['specular_fwhm_deg']:.1f} deg",
                 f"{ang['wide_reflector_5mm']['max_step_deg']:.1f} deg",
                 str(ang["wide_reflector_5mm"]["n_angles"])],
                ["2 mm", f"{ang['narrow_reflector_2mm']['specular_fwhm_deg']:.1f} deg",
                 f"{ang['narrow_reflector_2mm']['max_step_deg']:.1f} deg",
                 str(ang["narrow_reflector_2mm"]["n_angles"])]]))
    add("")
    add(f"**Sweeping in 5 degree steps can step straight over a "
        f"{ang['wide_reflector_5mm']['specular_fwhm_deg']:.1f} degree specular peak and "
        f"close a live mechanism.** Use "
        f"{ang['wide_reflector_5mm']['max_step_deg']:.1f} degree steps or finer over "
        f"+/-40 degrees. Do not restrict the sweep to the inherited 20-53 degree range: "
        f"that was an estimator stress test, not an access result.")
    add("")
    apr = r["aperture"]
    add("The aperture ladder is a second, independent mechanism discriminator, and it costs "
        "one afternoon: a diffuse return grows with aperture area, a specular return that "
        "already misses the aperture does not grow at all.")
    add("")
    add(_table(["Aperture (mm)"] + [f"{a*1000:.1f}" for a in apr["apertures_m"]],
               [["Diffuse prediction (dB)"] + [f"{d:+.1f}" for d in apr["diffuse_prediction_db"]],
                ["Specular prediction (dB)"] + [f"{s:+.1f}" for s in apr["specular_prediction_db"]]]))
    add("")

    # frequency
    fr = r["frequency"]
    add("### 5.5 Frequency: every mechanism prefers the low end, by very different amounts")
    add("")
    add(f"Below {fr['f0_min_resolution_hz']/1e6:.1f} MHz the axial resolution can no longer "
        f"separate the feature from a wall echo {fr['wall_separation_req_m']*1e3:.1f} mm "
        f"away, so those columns are struck out rather than won. That floor is computed at "
        f"the 60% fractional bandwidth used in this sweep; with the "
        f"{bw['recommended_frac_bw']*100:.0f}% fractional element recommended above it "
        f"falls to {bw['f0_floor_at_recommended_bw_hz']/1e6:.1f} MHz, because resolution is "
        f"set by absolute bandwidth rather than by centre frequency.")
    add("")
    hdr = ["Mechanism"] + [("~~" + f"{f/1e6:.0f}" + "~~" if not ok else f"{f/1e6:.0f}")
                           + " MHz" for f, ok in zip(fr["f_hz"], fr["permitted"])]
    add(_table(hdr + ["Best usable", "Penalty across the usable band"],
               [[m.key] + [f"{v:.0f}" for v in fr["median_fbr_db"][m.key]]
                + [f"**{fr['best_f_hz'][m.key]/1e6:.0f} MHz**",
                   f"{fr['penalty_across_band_db'][m.key]:.0f} dB"] for m in ALL]))
    add("")
    spread = fr["penalty_across_band_db"]
    hardest = max(spread, key=lambda k: spread[k])
    softest = min(spread, key=lambda k: spread[k])
    add(f"Median FBR in dB at the favourable background. Frequency trades three ways and "
        f"differently per mechanism: attenuation rises linearly with f over a two-way "
        f"centimetre path, a graded fluid edge is suppressed once kL > 1 so higher f hurts "
        f"M2 twice, and diffuse scattering rises as f^4 until 2kL > 1 and then flattens.")
    add("")
    add(f"Every mechanism prefers the bottom of the resolution-permitted band, so the "
        f"ranking does not decide the element. **What decides it is the penalty for going "
        f"high, which differs by {spread[hardest]-spread[softest]:.0f} dB across "
        f"mechanisms** — {hardest} loses {spread[hardest]:.0f} dB across the usable band "
        f"while {softest} loses only {spread[softest]:.0f} dB. A single centre frequency "
        f"therefore silently weights the screen towards whichever mechanism tolerates it. "
        f"The answer is the broadest available bandwidth centred at the low end of the "
        f"permitted range, with sub-band analysis in post-processing so each mechanism is "
        f"read at the frequency that suits it.")
    add("")
    add("One caveat on reading that table: M4's frequency dependence is **non-monotonic**, "
        "because the two wall surfaces interfere as sin(kh). Part of its apparent penalty "
        "is an interference null rather than attenuation, and the null moves with the "
        "lumen opening. That is not a reason to discount the column — it is a second, "
        "independent reason to measure across a band rather than at a point, and it is a "
        "sharp prediction: M4's return should show frequency nulls that shift as the "
        "lumen opens, which no other mechanism produces.")
    add("")

    # precision margin
    add("### 5.6 Displacement precision is not the binding constraint")
    add("")
    add(_table(["Condition", "Cramer-Rao position std"],
               [[k, f"{v:.0f} um"] for k, v in r["precision_um"].items()]))
    add("")
    pf = r["precision_floor_fbr_db"]
    add(f"The frozen per-estimate precision budget is {r['precision_budget_um']:.0f} um. "
        f"Inverting the bound gives the FBR at which that budget is exactly met: "
        + ", ".join(f"{v:+.1f} dB at rho = {k.split('_')[1]}" for k, v in pf.items())
        + ".")
    add("")
    add(f"Two consequences. First, **the precision floor and the inherited estimator floor "
        f"nearly coincide** ({min(pf.values()):+.1f} to {max(pf.values()):+.1f} dB against "
        f"{r['estimator_floor_db']:+.0f} dB), so a feature sitting at the estimator floor "
        f"is trackable but *not* measurable to the declared accuracy — that band must be "
        f"reported indeterminate, not accepted. Second, at the frozen "
        f"{thr:+.0f} dB detection threshold the bound has 10-20x of margin, so "
        f"**bandwidth is set by clutter separation and mechanism discrimination, not by "
        f"precision, and the position-error budget will be consumed by registration and "
        f"motion correction rather than by the estimator.** That is where the engineering "
        f"effort belongs.")
    add("")

    # fluids
    add("### 5.7 Fluid preparation ladder")
    add("")
    fl = r["fluids"]
    add(_table(["dSG", "delta rho (kg/m^3)", "r_p range (dc/drho bracket)", "R_I (dB)"],
               [[f"{x['dsg']:.3f}", f"{x['delta_rho_kg_m3']:.1f}",
                 f"{x['r_p_range'][0]:.5f} – {x['r_p_range'][1]:.5f}",
                 f"{x['R_I_db_range'][0]:.1f} – {x['R_I_db_range'][1]:.1f}"]
                for x in fl["ladder"]]))
    add("")
    add(f"{fl['note']} The bracket alone spreads reflected intensity by "
        f"{fl['spread_db']:.1f} dB at every step.")
    add("")

    # closure
    add("## 6. Which bench result closes each mechanism")
    add("")
    add(f"Screening order — by rig build-up, then by how much uncertainty each "
        f"experiment removes: **{' -> '.join(r['screening_order'])}**")
    add("")
    add("Two questions are kept apart here, because confusing them produces invalid "
        "closures. *Decidable* asks whether the instrument can measure the level at which "
        "a detection would be claimed — if it cannot, a null is a statement about the "
        "receiver and closes nothing. *Informative* asks whether the modelled range "
        "straddles the threshold, so the experiment could go either way. A predicted null "
        "is still worth running, early and cheaply; it just is not where the uncertainty "
        "lives.")
    add("")
    add(_table(["", "Rig", "Decidable", "Informative", "Clears threshold"],
               [[f"**{row['key']}** {row['name']}", str(row["rig_rank"]),
                 "yes" if row["decidable"] else "**no**",
                 "yes" if row["informative"] else "no",
                 f"{row['detect_fraction_favourable']:.0%}"] for row in r["closure"]]))
    add("")
    for row in r["closure"]:
        add(f"### {row['key']} — {row['name']}")
        add("")
        add(f"- **Favourable configuration:** {row['favourable_config']}")
        add(f"- **Decisive measurement:** {row['decisive_measurement']}")
        add(f"- **Predicted FBR if live:** {row['predicted_if_live_db']} dB")
        add(f"- **Null prediction:** {row['null_prediction']}")
        add(f"- **Positive control (same session):** {row['positive_control']}")
        add(f"- **Closes when:** {row['closes_when']}")
        add(f"- **Does NOT close:** {row['does_not_close']}")
        add(f"- **Load-bearing unknowns:** {row['load_bearing_unknowns']}")
        add(f"- **Rig (build order {row['rig_rank']}):** {row['rig']}")
        add(f"- **Verdict:** {row['verdict']}")
        add("")

    # open items
    add("## 7. What this model does not establish")
    add("")
    for item in [
        "That native urine supplies any of these features. Every mechanism is conditional.",
        "That a transcutaneous window exists in a child. The depths here are inferred from "
        "anatomy descriptions, not from a measured 18-24 month cohort.",
        "That reflux is distinguishable from normal peristalsis. That requires the "
        "two-position trajectory, and peristalsis runs antegrade at "
        f"{lit.V_PERISTALSIS.lo*1000:.0f}-{lit.V_PERISTALSIS.hi*1000:.0f} mm/s against a "
        "retrograde feature speed that is unmeasured across two decades.",
        "Any clinical sensitivity, specificity or grade coverage.",
        "That the mechanisms can be combined. M6 is an interval whose destructive corner is "
        "weaker than its strongest component.",
    ]:
        add(f"- {item}")
    add("")
    add("## 8. Open reconciliation items")
    add("")
    add("- The inherited \"a purely smooth front must be roughly < 229 um at 5 MHz\" figure "
        "is not reproduced by any of the three profile conventions implemented here "
        f"(this model gives {r['m2_targets']['edge_f1_at_inherited_threshold']['p50']:.0f} um "
        "at f = 1 under the tanh convention at the inherited -10 dB threshold, with "
        "attenuation included, and "
        f"{r['m2_targets']['profile_shape_sensitivity_um']['linear']:.0f} um under the "
        "linear-ramp convention). Either the inherited convention or this one is wrong, "
        "and the difference is a factor of three in the "
        "hardest requirement the fluid-gradient mechanism has. Resolve before the sharpness "
        "criterion is used to close M2.")
    add(f"- The inherited budget's 1.1% / 10.5% sharp-fraction figures *are* reproduced "
        f"({r['m2_targets']['required_fG_inherited_conditions_p50']*100:.2f}% favourable) "
        f"once the threshold and propagation assumptions are matched, which confirms the two "
        f"models agree on everything except the propagation path and the threshold.")
    add("- The diffuse mechanism's predicted strength differs by more than 100 dB between a "
        "Gaussian and a Kolmogorov mixing spectrum. M3 must not be closed on the Gaussian "
        "assumption; the measured frequency exponent decides.")
    add("")
    return "\n".join(L)


def write(claim: FrozenClaim, out_md: str, out_json: str, n: int = 30000) -> dict[str, Any]:
    r = compute(claim, n=n)
    with open(out_md, "w") as f:
        f.write(render(claim, r))
    with open(out_json, "w") as f:
        json.dump(_jsonable(r), f, indent=2)
    return r


def _jsonable(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (bool, int, float, str)) or o is None:
        return o
    return str(o)
