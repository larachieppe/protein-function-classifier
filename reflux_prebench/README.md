# Reflux pre-bench: freeze the claim, then design the experiment

Two deliverables for the step between *design planning* and *evidence*, for the
ultrasound directional reflux-detection programme (pulse–echo reflux-feature tracking):

1. **[`claim/`](claim/)** — the frozen experimental claim. What counts as success,
   written down and hashed before any data exists.
2. **[`prebench/`](prebench/)** — the pre-bench literature model, whose only output is an
   **experimental specification**: [`outputs/experimental_specification.md`](outputs/experimental_specification.md).

> **This model is not evidence of clinical sensitivity.** It is not evidence of a native
> reflux signal, of a transcutaneous window in a child, or of any device performance. It
> turns published ranges and explicit unknowns into instrument requirements, bench
> sweeps and stop thresholds. Nothing in it is measured — that is the point of the bench.

## Run it

```bash
pip install numpy pyyaml            # scipy is deliberately not required
python -m prebench.cli claim        # validate and cost the frozen claim
python -m prebench.cli ledger       # every input, with its provenance
python -m prebench.cli spec         # regenerate the experimental specification
python -m pytest tests/ -q          # 58 tests
```

`spec` refuses to run against a claim that fails validation. That is intentional: a
specification derived from an inconsistent claim is worse than none.

## What the model found

| | |
|---|---|
| **The inherited link budget is reproduced to 0.1 dB** | …and in doing so recovers the two constants it never stated: background levels of −66.6 / −56.6 / −46.6 dB re a perfect reflector, and an implied dc/dρ of 1.46 (m/s)/(kg/m³), which is a *salt*-dominated composition. Urine is urea-dominated. |
| **The inherited budget omitted the propagation path** | Reinstating two-way attenuation at the declared depths multiplies the required leading-edge sharp fraction by 11×. Raising the threshold from the estimator floor to the frozen claim multiplies it by a further 6.3×. Together: ~1% → ~69%. |
| **Native-urine VFI (M1) is close to arithmetically excluded** | Urine would have to backscatter 8–800× whole blood, and the favourable end assumes 20 dB of clutter suppression against the ~5 dB the programme's own simulations achieved. One gate wholly inside flowing urine settles it, on the simplest rig in the programme. |
| **The urine–urine gradient (M2) is impossible over a third of its own uncertainty space** | Not merely demanding — the required product `f·G` exceeds 1, which no profile of any shape can supply. |
| **A collapsed lumen is not acoustically silent** | Two wall surfaces separated by h return `2·r·sin(kh)`, peaking at λ/4 = 77 µm — right inside the bracketed residual-film range. **Echo amplitude versus opening is non-monotonic, and opening can make the echo smaller.** A first-day test on the collapsible-channel rig. |
| **Angular sampling can close a live mechanism** | A specular lobe is 3.5° wide at 5 MHz off a 5 mm reflector. Sweeping in 5° steps can step straight over it. Use ≤ 1.2°. |
| **The provisional element does not cover the required depth sweep** | 42 mm focus at f/3.0 covers 32–52 mm; the distal, mid and proximal routes span 20–80 mm. That is 4 elements at f/3.0, or 7 at f/2.0 — a purchasing decision, made explicit now rather than discovered later. |
| **The inherited 5 MHz is too high** | Once the resolution floor (2.6 MHz, to separate the feature from a wall 0.5 mm away) is imposed, every mechanism prefers the bottom of the usable band — but the penalty for going high spans 96 dB between mechanisms (M2 loses 126 dB across the band, M5 loses 30 dB). A single centre frequency silently weights the screen towards whichever mechanism tolerates it. |
| **Displacement precision is not the binding constraint anywhere** | The Cramér–Rao bound has 10–20× margin at the detection threshold. The position budget will be consumed by registration and motion correction. That is where the engineering effort belongs. |
| **No single two-point separation works** | The recommended separation spans 2–59 mm across the unmeasured feature-speed range. The dynamic bench needs a *settable* second position on a surveyed stage, not a fixed two-transducer mount. A workable separation exists whenever the feature outlives ~3 onset-timing uncertainties — independently of its speed. |

## How it is put together

```
claim/frozen_claim.yaml     thresholds as data, content-hashed
claim/FROZEN_CLAIM.md       the same thresholds with their reasoning, for sign-off

prebench/uncertain.py       Q: a bracket + a provenance status. No bare constants.
prebench/literature.py      every input, 39 entries, 0 of them MEASURED
prebench/acoustics.py       impedance, reflection, graded profiles, beams, attenuation
prebench/mechanisms.py      M1-M6, separate forward models, never summed
prebench/estimator.py       Cramer-Rao bounds, PRF windows, sampling, dynamic range
prebench/requirements.py    the inverse direction: what must be true of the target
prebench/twopoint.py        where to put the two observation points
prebench/acquisition.py     the derived instrument specification
prebench/closure.py         which bench result closes each mechanism
prebench/claim.py           load, validate, hash and cost the frozen claim
prebench/report.py          renders the specification
```

Three rules are enforced structurally rather than by convention:

- **Nothing enters the model except through `literature.py`,** and every entry carries a
  status (`MEASURED` / `PUBLISHED` / `DERIVED` / `SIMULATED` / `ASSUMED` / `UNMEASURED`)
  and a citation. Nothing is `MEASURED`. The report prints the census.
- **Mechanisms are never summed.** M6 is the only place two meet, and it returns an
  *interval* whose destructive corner is weaker than its strongest component — so a
  composite hypothesis can never rescue a component that failed alone.
- **Impossible is reported as impossible.** Where a requirement exceeds what physics
  allows (a fraction above 1), the model returns `NaN` and the report says "no width
  works", rather than clipping to a plausible-looking number.

## The tests are the validation

Pre-bench there is no measurement to check against, so the test suite checks that the
model reproduces every quantitative claim in the source documents from first principles —
including the ones stated there without derivation: the illustrative reflection
coefficients, the 0.032 / 0.1% urine–tissue pair, all nine cells of the inherited
tolerable-capture-loss table, and the provisional element's 3.2–5.3 cm depth of field.

One test earned its place by failing: the assertion that displacement precision is
adequate at the inherited −10 dB estimator floor. It is not. The precision floor sits at
−9 to −4 dB, which is an independent reason for the frozen detection threshold to sit
above the estimator floor, and a band that must be reported indeterminate rather than
quietly accepted.

## What happens next

The specification's closure table gives the screening order, cheapest decisive experiment
first, and for each mechanism: the favourable configuration, the decisive measurement,
the predicted level if live, the null prediction, the same-session positive control, and
what the closure does *not* close.

Before any of it runs, the claim needs three sign-offs and its hash in the acquisition
log. Until then it is a proposal, and the numbers in it are exactly the right thing to
argue about.
