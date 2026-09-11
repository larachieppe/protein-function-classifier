"""Which bench result closes each mechanism -- and what it leaves open.

The closure table is generated rather than written by hand, so that the decision
threshold quoted in it is always the one in the frozen claim and always the one the
link-budget model produced for that mechanism's own favourable geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

from .claim import FrozenClaim
from .mechanisms import ALL, Mechanism
from .requirements import clamp, detect_fraction
from .scenarios import Scenario


@dataclass
class ClosureRow:
    key: str
    name: str
    favourable_config: str
    decisive_measurement: str
    predicted_if_live_db: str
    null_prediction: str
    closes_when: str
    does_not_close: str
    positive_control: str
    load_bearing_unknowns: str
    detect_fraction_favourable: float
    rig: str
    rig_rank: int
    decidable: bool
    informative: bool
    verdict: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Rig each mechanism needs, in build order. The screening order follows this, because
#: the cost of a bench experiment is dominated by the fixture it requires, not by the
#: acquisition itself.
RIG = {
    "M1": (1, "Uniform fluid loop, gate inside the fluid. Simplest rig in the programme."),
    "M2": (2, "Two-fluid loop with a controlled interface and concentration imaging."),
    "M3": (3, "Two-fluid loop plus flow control able to reach and confirm a turbulent regime."),
    "M4": (4, "Compliant collapsible channel against a wall-less control, with optical lumen truth."),
    "M5": (4, "Same compliant rig plus surveyed imposed motion and vibration controls."),
    "M6": (5, "No rig of its own. Runs on stored records from M2 and M4."),
}


FAVOURABLE_CONFIG = {
    "M1": ("Gate wholly inside homogeneous flowing urine, shallowest declared depth, "
           "no wall in gate, maximum legitimate coherent averaging"),
    "M2": ("dSG = 0.016 (top of the declared band), stationary then moving mismatched "
           "interface, normal incidence, shallowest declared depth"),
    "M3": ("dSG = 0.016 at the highest flow rate the declared waveform produces, "
           "turbulent regime confirmed, aperture ladder at fixed angle"),
    "M4": ("Compliant collapsible channel driven through a full opening cycle against "
           "a wall-less channel control, identical flow, pressure and background"),
    "M5": ("Pressure-only compliant wall with synchronised optical wall-position truth, "
           "against rigid-body translation and pump-vibration controls"),
    "M6": ("Not testable in isolation: runs only after M2 and M4 have each been "
           "measured separately with their own phase records"),
}

DECISIVE = {
    "M1": ("Backscatter coefficient of the fluid, in 1/(m sr), measured against the "
           "terminated-receiver noise floor with the seeded ladder as positive control"),
    "M2": ("The product f * G(k, L_edge): the fraction of the impedance step in the "
           "leading edge times that edge's profile factor, reported as one quantity"),
    "M3": ("The frequency exponent n of the return across the full band, plus the "
           "aperture-area scaling, both against the matched-fluid turbulent control"),
    "M4": ("Compliant-channel minus wall-less-channel RF difference, with optical "
           "lumen-area truth, as a function of opening separation h"),
    "M5": ("Ratio of reflux-attributable wall displacement to nuisance displacement, "
           "i.e. the common-mode motion rejection actually achieved"),
    "M6": ("The measured relative phase between the M2 and M4 contributions. Without it "
           "the composite is an interval, not a value"),
}

POSITIVE_CONTROL = {
    "M1": "Seeded calibrated particles at a known concentration, same session, same settings",
    "M2": "Stationary mismatched interface: proves the chain can see a boundary at all",
    "M3": "Seeded turbulent flow at a known scatterer concentration",
    "M4": "Optical confirmation that the lumen actually opened during the trial",
    "M5": "Imposed, surveyed wall displacement of known amplitude and direction",
    "M6": "None exists. That is the reason it cannot be tested first",
}


def build(claim: FrozenClaim, scenario_for: dict[str, Scenario],
          noise_floor_db: float = -100.0) -> list[ClosureRow]:
    thr = float(claim.threshold("detection", "fbr_min_db"))
    rows: list[ClosureRow] = []
    for m in ALL:
        sc = scenario_for[m.key]
        cond = sc.draw()
        res = m.evaluate(cond, thr)
        fbr = clamp(res.fbr_db)
        p10, p50, p90 = (float(np.percentile(fbr, q)) for q in (10, 50, 90))
        frac = detect_fraction(res.fbr_db, thr)

        # Two separate questions, routinely confused:
        #
        #  decidable   Can the instrument measure the level at which a detection WOULD be
        #              claimed? If the threshold level sits above the noise floor, a null
        #              at that level is a statement about the mechanism, not the receiver.
        #              This is what makes a closure experiment valid.
        #  informative Does the modelled range straddle the threshold, so the experiment
        #              could go either way? If the whole plausible range sits below the
        #              threshold, the experiment is a cheap confirmation of a predicted
        #              null -- still worth running, and worth running early, but it is not
        #              where the uncertainty is.
        threshold_level_db = float(np.median(cond.background_db)) + thr
        decidable = threshold_level_db >= noise_floor_db + 10.0
        p90_clears = p90 >= thr
        p10_clears = p10 >= thr
        informative = p90_clears and not p10_clears

        if not decidable:
            verdict = (f"NOT A VALID CLOSURE EXPERIMENT. The level at which a detection "
                       f"would be claimed ({threshold_level_db:.0f} dB) is within 10 dB of "
                       f"the assumed noise floor ({noise_floor_db:.0f} dB). A null would be "
                       f"a statement about the receiver. Fix the floor first.")
        elif informative:
            verdict = ("Informative: the modelled range straddles the threshold, so this "
                       "experiment can genuinely go either way. This is where the "
                       "uncertainty lives.")
        elif p10_clears:
            verdict = ("The model predicts this mechanism clears the threshold across its "
                       "whole modelled range. Treat a null as a model failure to "
                       "investigate, not as a closure.")
        else:
            verdict = ("The model predicts a null across the whole modelled range. Run it "
                       "early and cheaply as a confirmation; a positive result would be a "
                       "model failure worth understanding before anything else proceeds.")

        rig_rank, rig_desc = RIG[m.key]

        rows.append(ClosureRow(
            key=m.key,
            name=m.name,
            favourable_config=FAVOURABLE_CONFIG[m.key],
            decisive_measurement=DECISIVE[m.key],
            predicted_if_live_db=f"{p10:.0f} / {p50:.0f} / {p90:.0f} (10/50/90 pct)",
            null_prediction=m.null_prediction,
            closes_when=m.closes_when,
            does_not_close=m.does_not_close,
            positive_control=POSITIVE_CONTROL[m.key],
            load_bearing_unknowns=", ".join(m.load_bearing_unknowns) or "-",
            detect_fraction_favourable=frac,
            rig=rig_desc,
            rig_rank=rig_rank,
            decidable=bool(decidable),
            informative=bool(informative),
            verdict=verdict,
        ))
    return rows


def ordering(rows: list[ClosureRow]) -> list[str]:
    """Screening order: by rig, then by how much uncertainty the experiment removes.

    The cost of a bench experiment is dominated by the fixture it needs, not by the
    acquisition, so the order follows rig build-up. Within a rig, run the experiment
    whose outcome is least predictable first, because that is the one that can change
    the plan.
    """
    return [r.key for r in sorted(
        rows, key=lambda r: (r.rig_rank, -abs(0.5 - r.detect_fraction_favourable)))]
