"""The complete constant table for the pre-bench model.

Rules enforced here:

1.  Nothing enters the model that is not in this file.
2.  Every entry carries a Status.  Nothing in this programme is MEASURED yet.
3.  Brackets are honest.  Where the literature does not constrain a quantity for
    *urine in a paediatric ureter during reflux*, the bracket spans the plausible
    physical range and is marked UNMEASURED, even when that makes the bracket useless
    for prediction.  A useless bracket is the finding.

Source keys used below:
  NIDDK      NIDDK normal urinary-tract reference (anatomy).
  NCBI-URET  NCBI Bookshelf, "Anatomy, Abdomen and Pelvis: Ureter".
  ACEP       ACEP renal/bladder ultrasound guide (probe placement).
  PUS        Polish Ultrasound Society urinary-tract standard (bladder filling, gas).
  MSK-ART    "Artifacts in Musculoskeletal Ultrasonography: From Physics to Clinics".
  WHITFIELD  Whitfield et al., normal individual ureteric activity in man (1993).
  FRY        Fry et al., "Control of urinary drainage and voiding" (2015).
  AIUM       Standard soft-tissue acoustic values (c, rho, alpha) as used in
             diagnostic ultrasound practice.
  DOC-TECH   The programme's own technical document (bench rationale), Sept 2026.
  DOC-PLAIN  The programme's own plain-English guide, Sept 2026.
  REPO-SIM   Model-internal results from this programme's existing simulation code.
"""

from __future__ import annotations

from .uncertain import Q, Registry, Shape, Status

R = Registry()
A = R.add


# ---------------------------------------------------------------------------
# 1. Bulk acoustic properties
# ---------------------------------------------------------------------------

C_TISSUE = A(Q("c_tissue", 1450.0, 1540.0, 1620.0, "m/s", Status.PUBLISHED, "AIUM",
               Shape.TRIANGULAR,
               "Soft-tissue longitudinal sound speed. Sets the depth scale and the "
               "range-gate to distance conversion."))

RHO_TISSUE = A(Q("rho_tissue", 1000.0, 1050.0, 1100.0, "kg/m^3", Status.PUBLISHED, "AIUM",
                 Shape.TRIANGULAR, "Soft-tissue density."))

Z_URETER_WALL = A(Q("Z_wall", 1.55, 1.675, 1.80, "MRayl", Status.PUBLISHED, "AIUM; DOC-TECH eq.29",
                    Shape.TRIANGULAR,
                    "Ureter-wall / perivesical tissue impedance. 1.675 is the illustrative "
                    "value used in the inherited link budget."))

C_URINE = A(Q("c_urine", 1505.0, 1540.0, 1575.0, "m/s", Status.PUBLISHED, "AIUM (water/saline at 37 C)",
              Shape.TRIANGULAR,
              "Urine sound speed at body temperature. Water at 37 C is ~1524 m/s; solutes "
              "raise it. Must be measured per preparation on the bench."))

RHO_URINE = A(Q("rho_urine", 1003.0, 1010.0, 1035.0, "kg/m^3", Status.PUBLISHED, "Clinical urine SG 1.003-1.035",
                Shape.TRIANGULAR, "Urine density from clinical specific-gravity range."))

Z_URINE = A(Q("Z_urine", 1.51, 1.571, 1.63, "MRayl", Status.DERIVED, "rho_urine * c_urine; DOC-TECH eq.29",
              Shape.TRIANGULAR, "Urine impedance. 1.571 is the inherited illustrative value."))

ALPHA_TISSUE = A(Q("alpha_tissue", 0.30, 0.50, 0.90, "dB/cm/MHz", Status.PUBLISHED, "AIUM",
                   Shape.TRIANGULAR,
                   "Soft-tissue attenuation coefficient, first power of frequency. "
                   "Applied over the two-way path."))

ALPHA_URINE = A(Q("alpha_urine", 0.0015, 0.0022, 0.0060, "dB/cm/MHz^2", Status.PUBLISHED, "AIUM (water-like)",
                  Shape.TRIANGULAR,
                  "Urine attenuation, quadratic in frequency. Negligible over centimetre "
                  "paths but retained so the ledger is complete."))

# The single most load-bearing unmeasured acoustic constant for the fluid-gradient
# mechanism.  Z = rho*c, so a specific-gravity difference only becomes an impedance
# difference through dc/drho.  See acoustics.delta_z_over_z.
DC_DRHO = A(Q("dc_drho", 0.50, 1.47, 2.20, "(m/s)/(kg/m^3)", Status.ASSUMED,
              "Bracket spans urea-dominated to salt-dominated solute composition; "
              "nominal 1.47 is the value implied by the inherited DOC-TECH Table 10",
              Shape.TRIANGULAR,
              "Rate of change of sound speed with density as urine solute load changes. "
              "BENCH MUST MEASURE rho and c independently; this constant then disappears."))

# ---------------------------------------------------------------------------
# 2. Programme-declared preparation band
# ---------------------------------------------------------------------------

DSG_MIN = A(Q("dsg_min", 0.002, 0.002, 0.002, "-", Status.ASSUMED, "DOC-TECH sec.2.1 declared band",
              Shape.POINT,
              "Low end of the declared specific-gravity contrast band. Load-bearing: it is "
              "the hardest declared acoustic contrast. NOT a proxy for low VUR grade."))

DSG_MAX = A(Q("dsg_max", 0.016, 0.016, 0.016, "-", Status.ASSUMED, "DOC-TECH sec.2.1 declared band",
              Shape.POINT, "High end of the declared specific-gravity contrast band."))

# ---------------------------------------------------------------------------
# 3. Native distributed backscatter
# ---------------------------------------------------------------------------

BSC_URINE = A(Q("bsc_urine", 1e-8, 1e-6, 1e-3, "1/(m sr)", Status.UNMEASURED,
                "No published backscatter coefficient exists for native urine at 5 MHz",
                Shape.LOGUNIFORM,
                "Backscatter coefficient of native urine. Five decades of ignorance. "
                "This single bracket decides whether native-fluid VFI is possible."))

BSC_BLOOD = A(Q("bsc_blood", 1e-3, 5e-3, 2e-2, "1/(m sr)", Status.PUBLISHED,
                "Whole-blood backscatter at 5-10 MHz",
                Shape.LOGUNIFORM,
                "Reference value. The seeded-particle positive control must land in this "
                "band to prove the receive chain works."))

# ---------------------------------------------------------------------------
# 4. Feature morphology (all unmeasured)
# ---------------------------------------------------------------------------

EDGE_WIDTH = A(Q("edge_width", 10e-6, 150e-6, 2e-3, "m", Status.UNMEASURED,
                 "No measurement of an in-vivo urine-urine transition profile exists",
                 Shape.LOGUNIFORM,
                 "Width scale of the LEADING EDGE of a urine-urine impedance transition. "
                 "Spans 'much sharper than a wavelength' to 'six wavelengths wide'. The "
                 "broad remainder of the transition is described by mix_zone_width; the two "
                 "must not be conflated, or the suppression is counted twice."))

MIX_ZONE_WIDTH = A(Q("mix_zone_width", 200e-6, 3e-3, 30e-3, "m", Status.UNMEASURED,
                     "No measurement of an in-vivo reflux mixing zone exists",
                     Shape.LOGUNIFORM,
                     "Total width of the mixing zone behind the leading edge. Contributes "
                     "essentially nothing to a compact echo at any usable frequency; it is "
                     "carried so the bench records it rather than folding it into the edge."))

SHARP_FRACTION = A(Q("sharp_fraction", 1e-3, 5e-2, 1.0, "-", Status.UNMEASURED,
                     "DOC-TECH sec.5.6: the fraction f is unmeasured",
                     Shape.LOGUNIFORM,
                     "Fraction f of the total impedance step carried inside the leading edge. "
                     "f=1 is a step; f->0 is a fully graded transition."))

MIX_CORR_LENGTH = A(Q("mix_corr_length", 50e-6, 500e-6, 5e-3, "m", Status.UNMEASURED,
                      "No measurement of reflux mixing-zone structure",
                      Shape.LOGUNIFORM,
                      "Correlation length of impedance fluctuations in a turbulent or mixing "
                      "zone. Sets the frequency dependence of the diffuse mechanism."))

MIX_Z_VARIANCE = A(Q("mix_z_variance", 1e-4, 1e-2, 1.0, "-", Status.UNMEASURED,
                     "Unmeasured; expressed as a fraction of the bulk (Delta Z / Z) step",
                     Shape.LOGUNIFORM,
                     "RMS relative impedance fluctuation inside the mixing zone, as a "
                     "fraction of the total bulk contrast."))

# ---------------------------------------------------------------------------
# 5. Ureter geometry and mechanics
# ---------------------------------------------------------------------------

LUMEN_COLLAPSED = A(Q("lumen_collapsed", 0.0, 100e-6, 300e-6, "m", Status.ASSUMED,
                      "NCBI-URET describes an apposed lumen; residual film thickness unmeasured",
                      Shape.TRIANGULAR,
                      "Residual fluid film thickness in an apposed ureter. Controls whether the "
                      "two wall-fluid surfaces cancel coherently."))

LUMEN_OPEN = A(Q("lumen_open", 1.0e-3, 2.5e-3, 5.0e-3, "m", Status.PUBLISHED, "NCBI-URET; NIDDK",
                 Shape.TRIANGULAR, "Open ureter lumen diameter during a reflux event."))

URETER_LENGTH = A(Q("ureter_length", 100e-3, 130e-3, 170e-3, "m", Status.PUBLISHED, "NIDDK; NCBI-URET",
                    Shape.TRIANGULAR, "Ureter length at 18-24 months. Hard upper bound on "
                                      "two-position separation."))

WALL_THICKNESS = A(Q("wall_thickness", 0.5e-3, 0.8e-3, 1.5e-3, "m", Status.PUBLISHED, "NCBI-URET",
                     Shape.TRIANGULAR, "Ureter wall thickness."))

# ---------------------------------------------------------------------------
# 6. Depths by access route (18-24 month child)
# ---------------------------------------------------------------------------

DEPTH_DISTAL = A(Q("depth_distal_uvj", 20e-3, 35e-3, 60e-3, "m", Status.ASSUMED,
                   "Inferred from NIDDK/ACEP/PUS descriptions; no qualified paediatric "
                   "depth distribution has been compiled",
                   Shape.TRIANGULAR,
                   "Skin-to-target depth, distal ureter / UVJ, anterior suprapubic route."))

DEPTH_PROXIMAL = A(Q("depth_proximal", 25e-3, 45e-3, 70e-3, "m", Status.ASSUMED,
                     "Inferred from NIDDK anatomy; posterior / flank route",
                     Shape.TRIANGULAR,
                     "Skin-to-target depth, proximal ureter / renal pelvis, posterior or "
                     "flank route."))

DEPTH_MID = A(Q("depth_mid", 30e-3, 50e-3, 80e-3, "m", Status.ASSUMED,
                "Inferred from NIDDK anatomy; PUS notes mid-ureter is usually gas-obscured",
                Shape.TRIANGULAR,
                "Skin-to-target depth, mid ureter. Access is usually blocked by bowel gas; "
                "depth is the lesser problem."))

# ---------------------------------------------------------------------------
# 7. Dynamics
# ---------------------------------------------------------------------------

V_PERISTALSIS = A(Q("v_peristalsis", 20e-3, 35e-3, 60e-3, "m/s", Status.PUBLISHED, "WHITFIELD; FRY",
                    Shape.TRIANGULAR,
                    "Antegrade peristaltic bolus propagation speed. This is the nuisance "
                    "signal a retrograde claim must be separated from."))

F_PERISTALSIS = A(Q("f_peristalsis", 2.0 / 60, 4.0 / 60, 6.0 / 60, "Hz", Status.PUBLISHED, "WHITFIELD; FRY",
                    Shape.TRIANGULAR,
                    "Peristaltic frequency. DOC-TECH withdraws the conversion of this into "
                    "an empty-lumen duty cycle."))

V_JET = A(Q("v_jet", 0.10, 0.25, 0.60, "m/s", Status.PUBLISHED, "Doppler ureteric-jet literature",
            Shape.TRIANGULAR, "Antegrade ureteric jet velocity at the orifice."))

V_FEATURE = A(Q("v_feature", 10e-3, 100e-3, 800e-3, "m/s", Status.UNMEASURED,
                "No measurement of retrograde feature propagation speed exists",
                Shape.LOGUNIFORM,
                "Propagation speed of the tracked retrograde feature. An opening front can "
                "travel faster than the fluid behind it, so this is not bounded by v_jet."))

T_FEATURE_LIFE = A(Q("t_feature_life", 50e-3, 400e-3, 3.0, "s", Status.UNMEASURED,
                     "Unmeasured; reflux is described as episodic and intermittent",
                     Shape.LOGUNIFORM,
                     "Time the feature remains recognisable. Together with v_feature this "
                     "bounds the usable two-position separation from above."))

RESP_EXCURSION = A(Q("resp_excursion", 3e-3, 8e-3, 20e-3, "m", Status.PUBLISHED,
                     "Respiratory organ excursion in children",
                     Shape.TRIANGULAR,
                     "Peak-to-peak tissue excursion from breathing. The dominant nuisance "
                     "displacement for the wall-motion mechanism."))

RESP_RATE = A(Q("resp_rate", 0.30, 0.45, 0.70, "Hz", Status.PUBLISHED, "Paediatric respiratory rate 18-42/min",
                Shape.TRIANGULAR, "Respiratory rate at 18-24 months."))

# ---------------------------------------------------------------------------
# 8. Inherited model-internal constants (SIMULATED - not evidence)
# ---------------------------------------------------------------------------

FBR_ESTIMATOR_FLOOR = A(Q("fbr_estimator_floor", -10.0, -10.0, -10.0, "dB", Status.SIMULATED,
                          "REPO-SIM; DOC-TECH sec.5.6 item 4",
                          Shape.POINT,
                          "Feature-to-background ratio at which the simplified 1-D RF tracker "
                          "stops working. A threshold on a synthetic input, not a physiological "
                          "prediction."))

BG_FAVOURABLE = A(Q("bg_favourable", -66.6, -66.6, -66.6, "dB re perfect reflector", Status.DERIVED,
                    "Reverse-engineered from DOC-TECH Table 10 (see acoustics.recover_inherited_backgrounds)",
                    Shape.POINT,
                    "Background level implied by the inherited 'favourable background' column. "
                    "It was never stated explicitly in the source document."))

BG_MIDDLE = A(Q("bg_middle", -56.6, -56.6, -56.6, "dB re perfect reflector", Status.DERIVED,
                "Reverse-engineered from DOC-TECH Table 10", Shape.POINT,
                "Background level implied by the inherited 'middle background' column."))

BG_WORST = A(Q("bg_worst", -46.6, -46.6, -46.6, "dB re perfect reflector", Status.DERIVED,
               "Reverse-engineered from DOC-TECH Table 10", Shape.POINT,
               "Background level implied by the inherited 'worst background' column."))

# ---------------------------------------------------------------------------
# 9. Provisional day-one instrument (DOC-TECH sec.4.3 'immediate execution state')
# ---------------------------------------------------------------------------

ELEMENT_DIAMETER = A(Q("element_diameter", 13.8e-3, 13.8e-3, 13.8e-3, "m", Status.ASSUMED,
                       "DOC-TECH sec.4.3 provisional specification", Shape.POINT,
                       "Provisional single-element aperture."))

ELEMENT_FOCUS = A(Q("element_focus", 42e-3, 42e-3, 42e-3, "m", Status.ASSUMED,
                    "DOC-TECH sec.4.3 provisional specification", Shape.POINT,
                    "Provisional geometric focus."))

F0_PROVISIONAL = A(Q("f0_provisional", 5e6, 5e6, 5e6, "Hz", Status.ASSUMED,
                     "DOC-TECH sec.5.6 item 5 uses 5 MHz", Shape.POINT,
                     "Provisional centre frequency. This model tests whether it is the right "
                     "choice rather than inheriting it."))


def ledger() -> Registry:
    return R
