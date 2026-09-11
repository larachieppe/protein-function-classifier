# Frozen experimental claim — fundamental physics bench

**Programme:** ultrasound directional reflux detection
**Method:** pulse–echo reflux-feature tracking
**Stage:** 3 — fundamental physics bench
**Version:** 1.0-draft · hash `d94fdd9347b1` · **status: awaiting sign-off, not yet frozen**

The machine-readable source of truth is [`frozen_claim.yaml`](frozen_claim.yaml). This
document explains *why* each number is what it is. Editing the prose here changes
nothing; editing a number in the YAML changes the hash and therefore the version.

**Freezing means:** three sign-offs present, and the content hash written into the
acquisition log **before the first trial**. Until then this is a proposal, and it should
be argued with. Every number below is a place where a reasonable person could disagree —
the point of writing them down now is that the disagreement happens before the data
exists rather than after.

---

## 1. The claim

> Under controlled bench conditions, a reflux-like event produces a repeatable raw-RF
> feature that can be observed at two registered ureter positions and correctly
> classified as retrograde.

That is deliberately narrow. It says nothing about children, nothing about urine,
nothing about grade, and nothing about diagnosis. It is the cheapest statement that, if
false, stops the programme before an array or an anthropomorphic phantom is bought.

**What the claim explicitly does not cover**

| Not claimed | Why it cannot be |
|---|---|
| Clinical sensitivity or specificity | The bench has no patients and no prevalence. |
| VUR grade coverage | Grade describes contrast extent during an examination; it is not an acoustic-contrast variable. |
| That a transcutaneous window exists in a child | Depth and angle here are laboratory variables, not access results. |
| That native urine supplies any of these features | Biological availability is unmeasured. The bench supplies a controlled analogue. |
| How often a ureter is apposed when reflux begins | Unmeasured. The lumen-opening mechanism is conditional on it. |

---

## 2. The three outcomes

Recorded **per side, per event**. Three states, not two.

**Positive — retrograde feature detected.** All of: a candidate clears detection; it is
attributed to a declared mechanism by its own controls; the same attributed feature
appears at both registered positions; arrival order is bladder-side first; the track
meets every tracking and accuracy threshold; motion and registration quality flags pass.

**Negative — no retrograde feature under adequate observability.** All of: both positions
observed for the whole declared event window; instrument-health and observability
preconditions passed; nothing cleared detection.

> A negative **requires demonstrated observability**. "Not seen" must never be recorded
> as "not present" without it. This is the single most important line in the document,
> because it is the one a tired operator at the end of a long day will most want to skip.

**Indeterminate — not adequately observed.** Any of: a position unobserved; saturation,
clipping or a gain change inside the gate; a candidate that cannot be attributed;
correlation, ambiguity or motion-quality flags failed; the feature left the field before
the minimum track accumulated; two candidates disagreeing on direction.

> Indeterminate is a **first-class result**, reported at the same prominence as the other
> two. Its rate is a primary output. A method that succeeds by discarding its hard cases
> has not succeeded.

---

## 3. The thresholds, and why

### Minimum feature-to-background ratio — **+6 dB**

Measured as integrated, gain-corrected energy in a gate fixed before unblinding, against
a matched *feature-absent* acquisition at identical gate, gain, bandwidth, filtering,
averaging and geometry. Never a single favourable voltage sample.

Why +6 dB and not the inherited −10 dB estimator floor:

- −10 dB is where the simplified 1-D tracker *stops working* on a synthetic input. A
  claim needs margin over the point of failure, not a claim pinned to it.
- Independently, the Cramér–Rao bound says the frozen 150 µm per-estimate precision is
  met only above about **−9 to −4 dB** (depending on correlation). Between the estimator
  floor and roughly −4 dB a feature is trackable but not measurable to the declared
  accuracy. +6 dB clears that band with 10–20× of margin.
- +6 dB is four times the background energy: an effect that survives a doubling of
  background amplitude.

The band **0 to +6 dB** is recorded as *marginal* and requires independent replication
before it counts. Below 0 dB is not a detection.

### Minimum SNR against electronic noise — **+20 dB**

So that a result is acoustically limited rather than instrument limited. Without this,
a null could be a statement about the receiver. It is also what sizes the digitiser:
the feature-to-background *ratio* needs its denominator measured with margin, which puts
the noise floor 20 dB below the background level, not below the feature.

### Maximum false-alarm rate — **5% candidate, 1% retrograde direction**

Against mechanism-absent matched background, and against antegrade and no-flow controls,
using the frozen detector with no re-tuning.

**These ceilings cost acquisitions, and the cost is part of the threshold:**

| Ceiling | Acquisitions with 0 failures | If 1 failure occurs |
|---|---|---|
| Candidate false alarm ≤ 5% | **72** | 110 |
| Retrograde direction false alarm ≤ 1% | **368** | 555 |

A 1% ceiling asserted on 30 control runs is not a threshold; it is a hope with a decimal
point. If 368 antegrade and no-flow controls are not affordable, the honest move is to
**raise the ceiling now** and say so, not to discover the problem during analysis.

### Minimum track duration — **10 consecutive qualified estimates, ≥ 20 ms, ≥ 1.0 mm, ≥ 3 resolution cells**

All four must hold. The displacement floor (1.0 mm) is set at more than 6× the frozen
per-estimate precision (150 µm) and about 4× the axial resolution at 3 MHz bandwidth
(257 µm), so a qualifying track cannot be confused with estimator noise or with a single
resolution cell's worth of jitter. Correlation must stay above 0.60 and the strongest
competing correlation peak must be below 0.70 of the primary.

### Required correct-direction rate — **≥ 90%, with a 95% lower bound ≥ 80%**

Over qualified retrograde events, with antegrade controls required to classify antegrade
at the same standard. **55 qualified retrograde events** are needed for an observed 90%
to have a lower confidence bound above 80%.

Zero direction-sign errors are permitted inside the qualified set: a qualified track that
points the wrong way is a failure of the qualification criteria, not a statistical
fluctuation to be averaged in.

### Acceptable position and speed error

| Quantity | Limit | Reasoning |
|---|---|---|
| Per-estimate displacement precision | 150 µm | Achievable with 10–20× margin at +6 dB FBR; sets the sampling and track-length floors. |
| Position RMS vs optical truth | 500 µm | One tenth of the smallest sensible two-point separation, and well inside a 2–5 mm lumen. |
| Position bias | 300 µm | Bias does not average out and propagates directly into speed. |
| Speed error | 20%, or 10 mm/s, whichever is larger | The floor matters: peristalsis runs at 20–60 mm/s, so a fixed percentage alone would be meaningless at low speeds. |
| Direction-sign errors in the qualified set | 0 | See above. |

These are dominated by **registration and motion correction, not by the estimator**. The
Cramér–Rao bound at the detection threshold is 17–57 µm. Effort spent on bandwidth beyond
what clutter separation needs is effort spent on the wrong problem.

### Repeatability across fluid preparations

**≥ 3 independent preparations per condition, ≥ 5 repeats each.** Between-preparation
spread of feature energy ≤ 3 dB, between-preparation variance no larger than
within-preparation variance, and — the binding requirement — **the outcome
(positive/negative/indeterminate) must not change between preparations.**

Three preparations is the minimum that separates between- from within-preparation
variance at all. Two cannot.

Every preparation must have ρ and c measured independently at the acquisition
temperature. Specific gravity is a preparation variable, never the calibration variable:
across the plausible solute-composition range, the same ΔSG spans about 5 dB of reflected
intensity.

### Rules for stopping an unsuccessful signal branch

Minimum 20 trials, positive control passing in the same session, 95% confidence, and a
10-day campaign cap per mechanism. Each mechanism closes **only in its own most
favourable declared geometry**, **only under its own conditions**, and each closure
statement must say what it does *not* close.

| | Closes when | Does **not** close |
|---|---|---|
| **M1** native backscatter | Gate wholly inside homogeneous flowing urine stays below the noise floor at maximum legitimate averaging, while the seeded ladder is recovered in the same session | Anything else. Urine with no distributed scatter can still reflect at a boundary or at an opening wall |
| **M2** urine–urine gradient | No gradient-attributable echo at ΔSG = 0.016 in favourable geometry, with the stationary mismatched interface proving the chain can see a boundary | M4 and M5, which need no fluid–fluid contrast. Failure only at ΔSG = 0.002 closes only the low-contrast corner and identifies **no** VUR grade |
| **M3** diffuse mixing | No return above the matched-fluid turbulent control across the ΔSG band at the flow rates the declared waveform produces, **and** the frequency exponent is inconsistent with diffuse scattering | The coherent mechanisms. A diffuse null is also a statement about the flow regime achieved |
| **M4** lumen opening | A collapsible tube driven through a full opening cycle produces no repeatable moving RF feature, with optical confirmation the lumen actually opened | How often a child's ureter is apposed when reflux begins — unmeasured, and this mechanism is conditional on it |
| **M5** wall motion | Retrograde wall-motion sequences cannot be separated from simulated antegrade peristalsis, fixture translation and pump vibration | The fluid mechanisms. Note the asymmetric risk: this is the mechanism most likely to pass a bench with no breathing, no bladder contraction and no hand tremor |
| **M6** composite | **Never on its own.** Closed only by the closure of every component | Anything. Its destructive corner is weaker than its strongest component, so it can never rescue a component that failed alone |

**Programme-level stop:** every candidate mechanism fails under its own most favourable
controlled geometry with all positive controls passing → stop the acoustic branch before
an array or an anthropomorphic phantom is purchased, and publish the measured null with
its link budget.

---

## 4. What would make this claim wrong

Written down now, so they cannot be reinterpreted later:

- A feature clearing every threshold in the **matched-fluid** control — the echo was
  never the gradient.
- A feature clearing every threshold under **rigid-body fixture translation alone**.
- Direction classified retrograde in **antegrade-flow** trials above the ceiling.
- The outcome **flipping between independent preparations** of the same nominal contrast.
- Feature energy tracking **receiver gain** rather than the declared mechanism variable.

---

## 5. Preconditions checked before any trial counts

Instrument impulse response, bandwidth and ring-down measured this session; gain
linearity verified with no clipping in the gate; noise floor recorded from terminated and
pre-trigger records; **no depth-varying TGC anywhere in the primary ratio**; timing jitter
and drift within limits. Fluid ρ and c measured per preparation at temperature, with
Z = ρc reported with uncertainty. Transducer pose mechanically surveyed; both observation
positions registered to the optical truth frame. Unprocessed RF and sample clock stored —
processed images are derived products. Algorithm version and blinded condition identifier
stored with every acquisition.

---

## 6. Sign-off

| Role | Name | Date |
|---|---|---|
| Physics lead | | |
| Clinical lead | | |
| Statistics reviewer | | |

Record the content hash in the acquisition log at sign-off. Re-run
`python -m prebench.cli claim` to recompute it.
