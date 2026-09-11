# Pre-bench experimental specification

**Programme:** ultrasound directional reflux detection — pulse-echo reflux-feature tracking  
**Generated:** 2026-09-11  
**Against frozen claim:** `1.0-draft` hash `d94fdd9347b1` — status *AWAITING SIGN-OFF -- not yet frozen*

> **What this document is.** The output of a literature-informed model whose only job is to design an experiment. It converts published ranges and explicit unknowns into instrument requirements, bench sweeps, and stop thresholds.
>
> **What it is not.** It is not evidence of clinical sensitivity, of a native reflux signal, of a transcutaneous window in a child, or of any device performance. Every mechanism below is modelled separately and none of the numbers may be combined into a single "reflux signal".

## 0. Provenance of every input

| Status | Count | Meaning |
| --- | --- | --- |
| MEASURED | 0 | measured on this programme's bench |
| PUBLISHED | 16 | external literature |
| DERIVED | 4 | computed from other entries |
| SIMULATED | 1 | this programme's own model output |
| ASSUMED | 10 | modelling choice, no evidential support |
| UNMEASURED | 8 | genuinely unknown, bracketed wide |

**Nothing is MEASURED yet.** That is the reason for the bench. The widest brackets, in decades of ignorance:

| Quantity | Bracket | Decades | Why it is load-bearing |
| --- | --- | --- | --- |
| bsc_urine | 1.00e-08 – 0.00100 1/(m sr) (nom 1.00e-06) | 5.0 | Backscatter coefficient of native urine |
| mix_z_variance | 1.00e-04 – 1.00 - (nom 0.0100) | 4.0 | RMS relative impedance fluctuation inside the mixing zone, as a fraction of the total bulk contrast |
| sharp_fraction | 0.00100 – 1.00 - (nom 0.0500) | 3.0 | Fraction f of the total impedance step carried inside the leading edge |
| edge_width | 1.00e-05 – 0.00200 m (nom 1.50e-04) | 2.3 | Width scale of the LEADING EDGE of a urine-urine impedance transition |
| mix_zone_width | 2.00e-04 – 0.0300 m (nom 0.00300) | 2.2 | Total width of the mixing zone behind the leading edge |
| mix_corr_length | 5.00e-05 – 0.00500 m (nom 5.00e-04) | 2.0 | Correlation length of impedance fluctuations in a turbulent or mixing zone |

## 1. What the frozen claim costs to test

| Threshold | Value | Acquisitions needed (0 failures) | If 1 failure |
| --- | --- | --- | --- |
| Candidate false alarm | <= 5% | 72 | 110 |
| Retrograde direction false alarm | <= 1% | 368 | 555 |
| Correct-direction rate | >= 90% (lower bound 80%) | 55 | - |

These counts are the claim. A false-alarm ceiling quoted without the trials that could detect a violation is not a threshold.

## 2. Reconciliation with the inherited link budget

The inherited tolerable-capture-loss table is reproduced exactly from first principles, which recovers the two constants it never stated:

| Row | r_p | Signal (dB) | This model (fav/mid/worst) | Published | Max error |
| --- | --- | --- | --- | --- | --- |
| empty-fill leading edge | 0.03200 | -29.9 | 46.7 / 36.7 / 26.7 | 46.7 / 36.7 / 26.7 | 0.00 dB |
| dSG = 0.016 fluid-fluid | 0.01552 | -36.2 | 40.4 / 30.4 / 20.4 | 40.5 / 30.5 / 20.5 | 0.09 dB |
| dSG = 0.002 fluid-fluid | 0.00194 | -54.2 | 22.4 / 12.4 / 2.4 | 22.5 / 12.5 / 2.5 | 0.15 dB |

- **Recovered background levels:** -66.6 dB, -56.6 dB, -46.6 dB re a perfect reflector. These three numbers carried the entire inherited budget and were never visible in it.
- **Recovered dc/drho:** 1.46 (m/s)/(kg/m^3). That is a salt-dominated composition. Urine is urea-dominated, so the inherited budget may be optimistic by several dB. The bench removes this constant entirely by measuring rho and c independently.
- **Under the inherited assumptions this model agrees.** At the inherited -10 dB estimator floor with no propagation path, the required sharp fraction comes out at 0.97%, against the inherited figure of 1.1%.
- **Attenuation was omitted from the inherited budget.** Reinstating two-way soft-tissue attenuation at the declared depths multiplies the required sharp fraction by 11x. Raising the detection threshold from the estimator floor (-10 dB) to the frozen claim (+6 dB) multiplies it by a further 6.3x. Together they move the requirement from 1.0% to 68%.

## 3. Per-mechanism link budget

Feature-to-background ratio in dB at 5 MHz, distal route, dSG = 0.016, across the full uncertainty space. Detection threshold from the frozen claim is **+6 dB**; the inherited estimator floor is -10 dB.

| Mechanism | FBR fav. bg (10/50/90 pct) | FBR worst bg (median) | Clears threshold | Frequency exponent |
| --- | --- | --- | --- | --- |
| M1 Native distributed backscatter | -78 / -56 / -34 | -76 | 0% | 0 to 4 (Rayleigh if scatterers are much smaller than a wavelength) |
| M2 Urine-urine impedance gradient | -200 / -78 / -14 | -98 | 1% | 0 for a step; falls steeply once k*L_edge > 1 |
| M3 Diffuse mixing / turbulence | -110 / -76 / -42 | -96 | 0% | 4, rolling off once 2*k*L_corr > 1 |
| M4 Lumen opening | -15 / 7 / 19 | -13 | 52% | 0, modulated by sin^2(k*h) two-surface interference until h exceeds the axial resolution |
| M5 Ureter-wall motion | 2 / 15 / 24 | -5 | 82% | 0 in amplitude; the information is carried by displacement, not energy |
| M6 Composite wall-fluid change | -15 / 6 / 19 | -14 | 51% | undefined: the sum of terms with different exponents and unknown phases |

*"Clears threshold" is the fraction of a deliberately flat prior over unmeasured brackets. It is a width-of-ignorance statistic, never a sensitivity. Levels are clamped at a -200 dB reporting floor: an entry at that value means "arbitrarily far below", not a computed level.*

## 4. The smallest signal the system must measure

**M1 — native distributed backscatter.** Required urine backscatter coefficient to clear threshold, as a function of how much clutter suppression is achieved:

| Clutter suppression | Required BSC 1/(m sr), median | vs whole blood |
| --- | --- | --- |
| 0 dB | 3.9 | 785x blood |
| 5 dB | 1.2 | 248x blood |
| 10 dB | 0.39 | 79x blood |
| 20 dB | 0.039 | 8x blood |

Whole blood sits at 1e-03 – 2e-02 1/(m sr). **Native urine would have to backscatter between 8x and 785x whole blood** for the VFI branch to clear the frozen threshold — and the favourable end of that range assumes 20 dB of clutter suppression, against the roughly 5 dB the programme's own simulations achieved with a longer coherent ensemble. One measurement — a gate wholly inside homogeneous flowing urine, against the terminated-receiver record — settles it, and it needs the simplest rig in the programme.

**M2 — urine-urine gradient.** The decisive quantity is the product `f x G(k, L_edge)` — the fraction of the impedance step carried in the leading edge, times that edge's profile factor. At dSG = 0.016 it must exceed **68%** (10th percentile 30%).

Because f and G are both fractions, their product cannot exceed 1. **In 33% of the sampled space the requirement exceeds 1, meaning no profile of any shape clears the threshold** — the mechanism is not merely demanding there, it is impossible.

| Sharp fraction | Required leading-edge width | Fraction of space where no width works |
| --- | --- | --- |
| f = 1 (whole step in the edge) | < 34 um (10–90 pct 15–50) | 33% |
| f = 0.1 | no width works | 100% |

That width also depends on an *unvalidated profile shape*: tanh 34 um, linear ramp 93 um, Gaussian 29 um — a factor of 3.2. **The bench must measure the profile shape, not only a width.** (For reference, lambda/4 at 5 MHz is 77 um.)

**M4 — lumen opening.** Two wall-fluid surfaces separated by h return `2|r| sin(kh)`, so the pair cancels only below about 26 um. The residual film in an apposed ureter is bracketed at 0–300 um, which straddles the quarter-wave maximum at 77 um. **A "collapsed" lumen is therefore not acoustically silent, and the echo change on opening can be negative.** Amplitude versus opening is non-monotonic — a direct, cheap, falsifiable prediction the collapsible-channel rig can test on its first day.

**M5 — wall motion.** Required common-mode motion rejection before a reflux-attributable wall displacement can be claimed:

| Reflux wall displacement | Rejection needed (10/50/90 pct) |
| --- | --- |
| 50 um | 42 dB / 46 dB / 50 dB |
| 200 um | 30 dB / 34 dB / 38 dB |
| 500 um | 22 dB / 26 dB / 30 dB |

This mechanism has the strongest echo and the weakest specificity. It is the one most likely to pass a bench that has no breathing, no bladder contraction and no operator hand tremor.

## 5. Derived instrument specification

| Quantity | Requirement | Set by |
| --- | --- | --- |
| Centre frequency | 4 MHz, not the inherited 5 MHz | every mechanism prefers the low end of the usable band and M2 prefers it by 126 dB (see 5.5); with the recommended bandwidth the resolution floor on centre frequency falls to 1.2 MHz, so this is a mechanism-coverage choice, not a resolution-limited one |
| -6 dB bandwidth | >= 1.5 MHz required; specify >= 5 MHz (125% fractional at 4 MHz) | resolve an open lumen 0.8 MHz; separate feature from wall 1.5 MHz; resolve a 100 um edge 7.7 MHz (desirable, not necessary); mechanism discrimination needs the band ratio, not the width |
| Band coverage | 2 – 7 MHz contiguous (3.5:1 band ratio) | frequency-exponent uncertainty 0.26 over that ratio separates specular (n=0) from diffuse (n=4) by more than 10 sigma |
| Sampling rate | >= 18.8 MS/s absolute; specify >= 25 MS/s, prefer 50 MS/s | Nyquist over the recommended band; interpolation bias is satisfied at 15 MS/s |
| ADC resolution | >= 14 bit (ENOB >= 11.9) | moving features cannot be coherently averaged, so instantaneous dynamic range must carry it |
| Instantaneous dynamic range | >= 73 dB | strongest in-gate echo -20 dB down to 20 dB below the background level (-67 dB), because feature-to-background is a ratio and the denominator must be measured with margin |
| Receiver noise floor | <= -87 dB re a perfect reflector (<= 234 uV rms if the reference echo is 1 V) | calibrated on day one against a flat plate, not an absolute pressure calculation |
| Time-gain compensation | None inside the primary ratio | a depth-varying gain makes feature-to-background unmeasurable |
| Axial resolution | 257 um at 3 MHz bandwidth; 154 um at 5 MHz | c / 2B |
| Usable depth range | 20 – 80 mm | distal, mid and proximal routes in an 18-24 month child |

**Depth coverage is a purchasing decision, and the provisional element does not make it.** A 42 mm focus at f/3.0 covers 32–52 mm at -6 dB — matching the programme's own stated 3.2–5.3 cm. The required sweep is 20–80 mm, which needs **4 fixed-focus elements at f/3.0** (foci 28, 42, 58, 73 mm) or 7 at f/2.0. Two-way attenuation across that sweep ranges from 10 to 40 dB at 5 MHz, so depth is not a second-order variable.

### 5.1 Sampling rate, measured rather than assumed

| Samples per cycle | fs at 5 MHz | Peak interpolation bias (samples) | as displacement |
| --- | --- | --- | --- |
| 2.5 | 12.5 MS/s | 2.6436 | 162.844 um |
| 3 | 15.0 MS/s | 0.1225 | 6.289 um |
| 4 | 20.0 MS/s | 0.0561 | 2.161 um |
| 6 | 30.0 MS/s | 0.0226 | 0.580 um |
| 8 | 40.0 MS/s | 0.0135 | 0.260 um |
| 10 | 50.0 MS/s | 0.0091 | 0.140 um |
| 16 | 80.0 MS/s | 0.0049 | 0.047 um |
| 20 | 100.0 MS/s | 0.0034 | 0.026 um |

Parabolic sub-sample interpolation of a shifted Gabor pulse, run at high SNR so the measured quantity is bias rather than noise. The criterion is 10% of the frozen per-estimate precision budget (15 um), which 3 samples/cycle already meets. **The binding constraint is therefore Nyquist over the 2.5-7.5 MHz band (18.8 MS/s), not interpolation.** Specify >= 25 MS/s for margin; 50 MS/s buys another order of magnitude of bias headroom for negligible cost, and 12.5 MS/s (2.5 samples/cycle) aliases the top of the band and fails catastrophically at 163 um.

### 5.2 Pulse-repetition frequency: where the window closes

PRF is bounded above by range ambiguity and below by per-pulse motion and the minimum track length. Phase-domain tracking (motion < lambda/4 per pulse) is the demanding case.

| Feature speed | Depth | PRF min (kHz) | PRF max (kHz) | Phase-domain feasible | Window-domain feasible |
| --- | --- | --- | --- | --- | --- |
| 20 mm/s | 35 mm | 0.3 | 17.6 | yes | yes |
| 20 mm/s | 60 mm | 0.3 | 10.3 | yes | yes |
| 20 mm/s | 80 mm | 0.3 | 7.7 | yes | yes |
| 100 mm/s | 35 mm | 1.3 | 17.6 | yes | yes |
| 100 mm/s | 60 mm | 1.3 | 10.3 | yes | yes |
| 100 mm/s | 80 mm | 1.3 | 7.7 | yes | yes |
| 300 mm/s | 35 mm | 3.9 | 17.6 | yes | yes |
| 300 mm/s | 60 mm | 3.9 | 10.3 | yes | yes |
| 300 mm/s | 80 mm | 3.9 | 7.7 | yes | yes |
| 500 mm/s | 35 mm | 6.5 | 17.6 | yes | yes |
| 500 mm/s | 60 mm | 6.5 | 10.3 | yes | yes |
| 500 mm/s | 80 mm | 6.5 | 7.7 | yes | yes |
| 800 mm/s | 35 mm | 10.4 | 17.6 | yes | yes |
| 800 mm/s | 60 mm | 10.4 | 10.3 | **no** | yes |
| 800 mm/s | 80 mm | 10.4 | 7.7 | **no** | yes |

**2 of 15 speed/depth combinations have no phase-domain PRF window at 5 MHz.** Where the window closes, the options are a lower centre frequency, a restricted depth, or envelope/window-domain tracking with its coarser precision. This must be decided before the digitiser is configured, not after a failed run.

### 5.3 Distance between the two observation points

| Onset-timing uncertainty | Recommended separation (10/50/90 pct) | Feasible fraction | Requires feature lifetime above |
| --- | --- | --- | --- |
| 2 ms | 2 / 5 / 29 mm | 95% | 6 ms |
| 10 ms | 2 / 11 / 59 mm | 95% | 30 ms |
| 20 ms | 3 / 16 / 65 mm | 92% | 60 ms |

| Feature speed | Separation for 1% timing-only wrong-direction rate |
| --- | --- |
| 20 mm/s | 0.7 mm |
| 100 mm/s | 3.3 mm |
| 500 mm/s | 16.4 mm |
| 800 mm/s | 26.3 mm |

The timing bound and the lifetime bound both scale with feature speed, so their ratio does not: **a workable separation exists whenever the feature lives longer than about three onset-timing uncertainties, independently of how fast it moves.** Speed only decides *where* in the window to put the points — and it is unmeasured across nearly two decades. The recommended separation therefore spans 2–59 mm.

**Hardware consequence:** the dynamic bench needs a *settable* second observation position on a surveyed translation stage spanning at least 2–40 mm, not a fixed two-transducer mount. A fixed separation chosen for fast features makes slow short-lived features indeterminate, and vice versa.

### 5.4 Angle and aperture sweeps

| Illuminated reflector width | Specular lobe FWHM | Max angular step | Angles over +/-40 deg |
| --- | --- | --- | --- |
| 5 mm | 3.5 deg | 1.2 deg | 69 |
| 2 mm | 8.8 deg | 2.9 deg | 29 |

**Sweeping in 5 degree steps can step straight over a 3.5 degree specular peak and close a live mechanism.** Use 1.2 degree steps or finer over +/-40 degrees. Do not restrict the sweep to the inherited 20-53 degree range: that was an estimator stress test, not an access result.

The aperture ladder is a second, independent mechanism discriminator, and it costs one afternoon: a diffuse return grows with aperture area, a specular return that already misses the aperture does not grow at all.

| Aperture (mm) | 4.0 | 6.0 | 9.0 | 13.8 | 19.0 |
| --- | --- | --- | --- | --- | --- |
| Diffuse prediction (dB) | +0.0 | +3.5 | +7.0 | +10.8 | +13.5 |
| Specular prediction (dB) | +0.0 | +0.0 | +0.0 | +0.0 | +0.0 |

### 5.5 Frequency: every mechanism prefers the low end, by very different amounts

Below 2.6 MHz the axial resolution can no longer separate the feature from a wall echo 0.5 mm away, so those columns are struck out rather than won. That floor is computed at the 60% fractional bandwidth used in this sweep; with the 125% fractional element recommended above it falls to 1.2 MHz, because resolution is set by absolute bandwidth rather than by centre frequency.

| Mechanism | ~~1~~ MHz | ~~2~~ MHz | 3 MHz | 4 MHz | 5 MHz | 7 MHz | 10 MHz | Best usable | Penalty across the usable band |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | -31 | -39 | -45 | -50 | -56 | -66 | -80 | **3 MHz** | 35 dB |
| M2 | -20 | -33 | -45 | -60 | -78 | -114 | -172 | **3 MHz** | 126 dB |
| M3 | -54 | -60 | -65 | -71 | -76 | -88 | -105 | **3 MHz** | 40 dB |
| M4 | 24 | 19 | 15 | 11 | 7 | -7 | -68 | **3 MHz** | 83 dB |
| M5 | 33 | 28 | 24 | 20 | 15 | 7 | -6 | **3 MHz** | 30 dB |
| M6 | 23 | 18 | 15 | 11 | 6 | -6 | -40 | **3 MHz** | 55 dB |

Median FBR in dB at the favourable background. Frequency trades three ways and differently per mechanism: attenuation rises linearly with f over a two-way centimetre path, a graded fluid edge is suppressed once kL > 1 so higher f hurts M2 twice, and diffuse scattering rises as f^4 until 2kL > 1 and then flattens.

Every mechanism prefers the bottom of the resolution-permitted band, so the ranking does not decide the element. **What decides it is the penalty for going high, which differs by 96 dB across mechanisms** — M2 loses 126 dB across the usable band while M5 loses only 30 dB. A single centre frequency therefore silently weights the screen towards whichever mechanism tolerates it. The answer is the broadest available bandwidth centred at the low end of the permitted range, with sub-band analysis in post-processing so each mechanism is read at the frequency that suits it.

One caveat on reading that table: M4's frequency dependence is **non-monotonic**, because the two wall surfaces interfere as sin(kh). Part of its apparent penalty is an interference null rather than attenuation, and the null moves with the lumen opening. That is not a reason to discount the column — it is a second, independent reason to measure across a band rather than at a point, and it is a sharp prediction: M4's return should show frequency nulls that shift as the lumen opens, which no other mechanism produces.

### 5.6 Displacement precision is not the binding constraint

| Condition | Cramer-Rao position std |
| --- | --- |
| FBR -10 dB, rho 0.6 — at the estimator floor, heavy decorrelation | 255 um |
| FBR +0 dB, rho 0.8 — at 0 dB FBR, good correlation | 32 um |
| FBR +6 dB, rho 0.8 — at the frozen threshold, good correlation | 17 um |
| FBR +6 dB, rho 0.3 — at the frozen threshold, severe decorrelation | 56 um |

The frozen per-estimate precision budget is 150 um. Inverting the bound gives the FBR at which that budget is exactly met: -9.4 dB at rho = 0.9, -7.4 dB at rho = 0.6, -3.5 dB at rho = 0.3.

Two consequences. First, **the precision floor and the inherited estimator floor nearly coincide** (-9.4 to -3.5 dB against -10 dB), so a feature sitting at the estimator floor is trackable but *not* measurable to the declared accuracy — that band must be reported indeterminate, not accepted. Second, at the frozen +6 dB detection threshold the bound has 10-20x of margin, so **bandwidth is set by clutter separation and mechanism discrimination, not by precision, and the position-error budget will be consumed by registration and motion correction rather than by the estimator.** That is where the engineering effort belongs.

### 5.7 Fluid preparation ladder

| dSG | delta rho (kg/m^3) | r_p range (dc/drho bracket) | R_I (dB) |
| --- | --- | --- | --- |
| 0.002 | 2.0 | 0.00131 – 0.00242 | -57.6 – -52.3 |
| 0.004 | 4.0 | 0.00263 – 0.00484 | -51.6 – -46.3 |
| 0.006 | 6.0 | 0.00394 – 0.00726 | -48.1 – -42.8 |
| 0.008 | 8.0 | 0.00526 – 0.00967 | -45.6 – -40.3 |
| 0.010 | 10.0 | 0.00657 – 0.01209 | -43.6 – -38.3 |
| 0.013 | 13.0 | 0.00855 – 0.01572 | -41.4 – -36.1 |
| 0.016 | 16.0 | 0.01052 – 0.01935 | -39.6 – -34.3 |

Every preparation must have rho and c measured independently at the acquisition temperature. The dc/drho bracket alone spreads the reflected intensity by about 5 dB at every step, which is why specific gravity cannot be the calibration variable. The bracket alone spreads reflected intensity by 5.3 dB at every step.

## 6. Which bench result closes each mechanism

Screening order — by rig build-up, then by how much uncertainty each experiment removes: **M1 -> M2 -> M3 -> M5 -> M4 -> M6**

Two questions are kept apart here, because confusing them produces invalid closures. *Decidable* asks whether the instrument can measure the level at which a detection would be claimed — if it cannot, a null is a statement about the receiver and closes nothing. *Informative* asks whether the modelled range straddles the threshold, so the experiment could go either way. A predicted null is still worth running, early and cheaply; it just is not where the uncertainty lives.

|  | Rig | Decidable | Informative | Clears threshold |
| --- | --- | --- | --- | --- |
| **M1** Native distributed backscatter | 1 | yes | no | 0% |
| **M2** Urine-urine impedance gradient | 2 | yes | no | 1% |
| **M3** Diffuse mixing / turbulence | 3 | yes | no | 0% |
| **M4** Lumen opening | 4 | yes | yes | 52% |
| **M5** Ureter-wall motion | 4 | yes | yes | 82% |
| **M6** Composite wall-fluid change | 5 | yes | yes | 51% |

### M1 — Native distributed backscatter

- **Favourable configuration:** Gate wholly inside homogeneous flowing urine, shallowest declared depth, no wall in gate, maximum legitimate coherent averaging
- **Decisive measurement:** Backscatter coefficient of the fluid, in 1/(m sr), measured against the terminated-receiver noise floor with the seeded ladder as positive control
- **Predicted FBR if live:** -78 / -56 / -34 (10/50/90 pct) dB
- **Null prediction:** Gate placed wholly inside homogeneous flowing urine returns nothing above the electronic noise floor at maximum usable gain.
- **Positive control (same session):** Seeded calibrated particles at a known concentration, same session, same settings
- **Closes when:** Bulk-fluid return is below the electronic noise floor after the maximum legitimate coherent averaging, in the most favourable geometry, while the seeded-particle positive control at a known concentration is recovered in the same session with the same settings.
- **Does NOT close:** Nothing about the other five mechanisms. A urine with no distributed scatter can still reflect at a boundary with a second fluid or at an opening lumen wall.
- **Load-bearing unknowns:** bsc_urine
- **Rig (build order 1):** Uniform fluid loop, gate inside the fluid. Simplest rig in the programme.
- **Verdict:** The model predicts a null across the whole modelled range. Run it early and cheaply as a confirmation; a positive result would be a model failure worth understanding before anything else proceeds.

### M2 — Urine-urine impedance gradient

- **Favourable configuration:** dSG = 0.016 (top of the declared band), stationary then moving mismatched interface, normal incidence, shallowest declared depth
- **Decisive measurement:** The product f * G(k, L_edge): the fraction of the impedance step in the leading edge times that edge's profile factor, reported as one quantity
- **Predicted FBR if live:** -200 / -78 / -14 (10/50/90 pct) dB
- **Null prediction:** Acoustically matched fluids in motion produce no stable feature attributable to a fluid-fluid gradient, only apparatus and wall residuals.
- **Positive control (same session):** Stationary mismatched interface: proves the chain can see a boundary at all
- **Closes when:** No gradient-attributable echo at dSG = 0.016 in the most favourable controlled geometry, with the stationary mismatched interface confirming in the same session that the chain can see a boundary at all.
- **Does NOT close:** The lumen-opening and wall-motion mechanisms, which do not require any fluid-fluid contrast. Failure only at dSG = 0.002 closes nothing except the low-contrast corner and does NOT identify which VUR grades would be missed.
- **Load-bearing unknowns:** dc_drho, sharp_fraction, edge_width
- **Rig (build order 2):** Two-fluid loop with a controlled interface and concentration imaging.
- **Verdict:** The model predicts a null across the whole modelled range. Run it early and cheaply as a confirmation; a positive result would be a model failure worth understanding before anything else proceeds.

### M3 — Diffuse mixing / turbulence

- **Favourable configuration:** dSG = 0.016 at the highest flow rate the declared waveform produces, turbulent regime confirmed, aperture ladder at fixed angle
- **Decisive measurement:** The frequency exponent n of the return across the full band, plus the aperture-area scaling, both against the matched-fluid turbulent control
- **Predicted FBR if live:** -110 / -76 / -42 (10/50/90 pct) dB
- **Null prediction:** Angular response is broad and flat rather than peaked; return scales with aperture area; matched fluids in turbulent flow return nothing.
- **Positive control (same session):** Seeded turbulent flow at a known scatterer concentration
- **Closes when:** No return above the matched-fluid turbulent control across the whole dSG band at the flow rates the voiding waveform actually produces.
- **Does NOT close:** The coherent mechanisms. A diffuse null is expected wherever the transition stays laminar, so a null here is a statement about the flow regime as much as about acoustics.
- **Load-bearing unknowns:** mix_z_variance, mix_corr_length, dc_drho
- **Rig (build order 3):** Two-fluid loop plus flow control able to reach and confirm a turbulent regime.
- **Verdict:** The model predicts a null across the whole modelled range. Run it early and cheaply as a confirmation; a positive result would be a model failure worth understanding before anything else proceeds.

### M4 — Lumen opening

- **Favourable configuration:** Compliant collapsible channel driven through a full opening cycle against a wall-less channel control, identical flow, pressure and background
- **Decisive measurement:** Compliant-channel minus wall-less-channel RF difference, with optical lumen-area truth, as a function of opening separation h
- **Predicted FBR if live:** -15 / 7 / 19 (10/50/90 pct) dB
- **Null prediction:** A wall-less channel and a compliant collapsible channel, run under identical flow, pressure, acoustic and background conditions, return the same waveform.
- **Positive control (same session):** Optical confirmation that the lumen actually opened during the trial
- **Closes when:** A controlled collapsible tube driven through a full opening cycle produces no repeatable moving RF feature in the most favourable controlled geometry, with synchronised optical imaging confirming the lumen actually opened.
- **Does NOT close:** How often a child's ureter is apposed when reflux begins. That prevalence is unmeasured and this mechanism is conditional on it. A positive result here is not evidence of a urine-urine interface.
- **Load-bearing unknowns:** lumen_collapsed, z_wall
- **Rig (build order 4):** Compliant collapsible channel against a wall-less control, with optical lumen truth.
- **Verdict:** Informative: the modelled range straddles the threshold, so this experiment can genuinely go either way. This is where the uncertainty lives.

### M5 — Ureter-wall motion

- **Favourable configuration:** Pressure-only compliant wall with synchronised optical wall-position truth, against rigid-body translation and pump-vibration controls
- **Decisive measurement:** Ratio of reflux-attributable wall displacement to nuisance displacement, i.e. the common-mode motion rejection actually achieved
- **Predicted FBR if live:** 2 / 15 / 24 (10/50/90 pct) dB
- **Null prediction:** Under pressure-only actuation with no reflux, the wall echo still moves. The reflux-specific component is the ordered retrograde propagation of that motion, not its presence.
- **Positive control (same session):** Imposed, surveyed wall displacement of known amplitude and direction
- **Closes when:** Retrograde wall-motion sequences cannot be separated from simulated antegrade peristalsis, fixture translation and pump vibration at the frozen decision threshold.
- **Does NOT close:** The fluid mechanisms. Note also that this mechanism is the one most likely to succeed on the bench and fail clinically, because the bench has no breathing, no bladder contraction and no operator hand tremor.
- **Load-bearing unknowns:** z_wall
- **Rig (build order 4):** Same compliant rig plus surveyed imposed motion and vibration controls.
- **Verdict:** Informative: the modelled range straddles the threshold, so this experiment can genuinely go either way. This is where the uncertainty lives.

### M6 — Composite wall-fluid change

- **Favourable configuration:** Not testable in isolation: runs only after M2 and M4 have each been measured separately with their own phase records
- **Decisive measurement:** The measured relative phase between the M2 and M4 contributions. Without it the composite is an interval, not a value
- **Predicted FBR if live:** -15 / 6 / 19 (10/50/90 pct) dB
- **Null prediction:** None available. A composite hypothesis makes no null prediction of its own, which is precisely why it must not be tested first.
- **Positive control (same session):** None exists. That is the reason it cannot be tested first
- **Closes when:** Never on its own. This mechanism is closed only by the closure of every component, and it is opened only by evidence that two measured components co-occur with a stable phase relationship.
- **Does NOT close:** Anything. The destructive corner of the composite interval is weaker than the strongest component alone, so a composite claim cannot rescue a failed component.
- **Load-bearing unknowns:** relative phase (entirely unconstrained)
- **Rig (build order 5):** No rig of its own. Runs on stored records from M2 and M4.
- **Verdict:** Informative: the modelled range straddles the threshold, so this experiment can genuinely go either way. This is where the uncertainty lives.

## 7. What this model does not establish

- That native urine supplies any of these features. Every mechanism is conditional.
- That a transcutaneous window exists in a child. The depths here are inferred from anatomy descriptions, not from a measured 18-24 month cohort.
- That reflux is distinguishable from normal peristalsis. That requires the two-position trajectory, and peristalsis runs antegrade at 20-60 mm/s against a retrograde feature speed that is unmeasured across two decades.
- Any clinical sensitivity, specificity or grade coverage.
- That the mechanisms can be combined. M6 is an interval whose destructive corner is weaker than its strongest component.

## 8. Open reconciliation items

- The inherited "a purely smooth front must be roughly < 229 um at 5 MHz" figure is not reproduced by any of the three profile conventions implemented here (this model gives 69 um at f = 1 under the tanh convention at the inherited -10 dB threshold, with attenuation included, and 93 um under the linear-ramp convention). Either the inherited convention or this one is wrong, and the difference is a factor of three in the hardest requirement the fluid-gradient mechanism has. Resolve before the sharpness criterion is used to close M2.
- The inherited budget's 1.1% / 10.5% sharp-fraction figures *are* reproduced (0.97% favourable) once the threshold and propagation assumptions are matched, which confirms the two models agree on everything except the propagation path and the threshold.
- The diffuse mechanism's predicted strength differs by more than 100 dB between a Gaussian and a Kolmogorov mixing spectrum. M3 must not be closed on the Gaussian assumption; the measured frequency exponent decides.
