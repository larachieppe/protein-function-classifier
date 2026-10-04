"""
Bioheat exploration: can a thermal tracer reveal the direction of urine flow in the
ureter, i.e. detect vesicoureteral reflux (VUR) without ionising radiation?

Two experiments, both built on the Pennes bioheat equation coupled to advection of
heat by urine inside the ureter lumen:

    rho*c (dT/dt + u . grad T) = div(k grad T) + w_b*rho_b*c_b*(T_a - T) + Q

  A. "Thermal time-of-flight": briefly heat a small spot on the ureter (e.g. focused
     ultrasound) and watch two thermometry voxels, one kidney-side and one
     bladder-side. Moving urine carries the heat plume towards one of them, so the
     sign of the asymmetry gives the flow direction.

  B. "Thermal VCUG": fill the bladder with saline a few degrees off body temperature
     (as a voiding cystourethrogram already does with contrast). If urine refluxes
     during voiding, the temperature anomaly is carried up the ureter into the renal
     pelvis, where it can be picked up by MR thermometry or microwave radiometry.

All temperatures are deltas relative to arterial/core temperature (37 C). The
problem is linear in the source, so heating is simulated with a unit source and
rescaled afterwards.

Run:  python bioheat_reflux.py      (writes figures + results.json next to this file)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- material values
# Urine ~ water. Tissue ~ generic retroperitoneal soft tissue (muscle/fat mix).
URINE = dict(k=0.60, rho_c=1000 * 4180, perf=0.0)
WALL = dict(k=0.52, rho_c=1050 * 3700, perf=0.002)       # ureteral wall, well perfused
TISSUE = dict(k=0.45, rho_c=1000 * 3300, perf=0.0008)    # periureteral fat/muscle
RHO_C_BLOOD = 1050 * 3617                                # J/(m^3 K)
ALPHA_URINE = URINE["k"] / URINE["rho_c"]                # ~1.4e-7 m^2/s


@dataclass
class Ureter:
    radius: float = 2.0e-3        # lumen radius [m]; ~1.5-3 mm normal, 4-8 mm dilated (VUR IV-V)
    wall: float = 0.8e-3          # wall thickness [m]
    r_max: float = 12e-3          # radial extent of the model [m]
    dr: float = 0.2e-3
    dz: float = 0.4e-3


def build_grid(geo: Ureter, z_min: float, z_max: float):
    nr = int(round(geo.r_max / geo.dr))
    nz = int(round((z_max - z_min) / geo.dz))
    r = (np.arange(nr) + 0.5) * geo.dr
    z = z_min + (np.arange(nz) + 0.5) * geo.dz
    lumen = r < geo.radius
    wall = (r >= geo.radius) & (r < geo.radius + geo.wall)
    props = {}
    for name in ("k", "rho_c", "perf"):
        v = np.full(nr, TISSUE[name], dtype=float)
        v[wall] = WALL[name]
        v[lumen] = URINE[name]
        props[name] = v
    return r, z, lumen, props


def simulate(geo: Ureter, mean_velocity, t_end: float, z_range=(-40e-3, 40e-3),
             source=None, inlet_temp=None, record=None, dt_max=0.05):
    """Explicit finite-volume solver on an axisymmetric (r, z) grid.

    mean_velocity: float or callable t -> float, mean lumen velocity [m/s]
                   (+ = towards the kidney, i.e. reflux; - = normal antegrade flow).
    source:        (Q(r,z) array [W/m^3], t_on, t_off) or None.
    inlet_temp:    callable t -> dT of urine entering the lumen at the upstream end.
    record:        dict name -> callable(T, r, z) -> float, sampled every 0.1 s.
    """
    r, z, lumen, p = build_grid(geo, *z_range)
    nr, nz = len(r), len(z)
    dr, dz = geo.dr, geo.dz
    U = mean_velocity if callable(mean_velocity) else (lambda t, v=mean_velocity: v)
    profile = np.where(lumen, 2.0 * (1 - (r / geo.radius) ** 2), 0.0)  # Poiseuille, mean = 1

    k_face = 0.5 * (p["k"][1:] + p["k"][:-1])               # radial faces i+1/2
    r_face = r[:-1] + 0.5 * dr
    rho_c = p["rho_c"][:, None]
    W = (p["perf"] * RHO_C_BLOOD)[:, None]
    k = p["k"][:, None]

    u_peak = 2 * max(abs(U(t)) for t in np.linspace(0, t_end, 200))
    alpha_max = (p["k"] / p["rho_c"]).max()
    dt = min(dt_max, 0.2 / (alpha_max * (1 / dr**2 + 1 / dz**2)),
             0.5 * dz / u_peak if u_peak > 0 else np.inf)
    n_steps = int(np.ceil(t_end / dt))
    dt = t_end / n_steps

    T = np.zeros((nr, nz))
    samples = {name: [] for name in (record or {})}
    times = []
    sample_every = max(1, int(round(0.1 / dt)))
    peak_T = 0.0
    cem43 = np.zeros((nr, nz))  # thermal dose (equivalent minutes at 43 C), body at 37 C

    for n in range(n_steps + 1):
        t = n * dt
        if record and n % sample_every == 0:
            times.append(t)
            for name, fn in record.items():
                samples[name].append(fn(T, r, z))
        if n == n_steps:
            break

        # radial diffusion: (1/r) d/dr (r k dT/dr)
        flux_r = r_face[:, None] * k_face[:, None] * (T[1:] - T[:-1]) / dr
        div_r = np.zeros_like(T)
        div_r[:-1] += flux_r
        div_r[1:] -= flux_r
        div_r[-1] += (r[-1] + dr / 2) * k[-1] * (0 - T[-1]) / (dr / 2)  # far field held at body temp
        div_r /= r[:, None] * dr

        # axial diffusion with ghost cells (Dirichlet 0 / inlet value, outflow zero-gradient)
        u_now = U(t)
        Tin = inlet_temp(t) if inlet_temp else 0.0
        left = np.zeros(nr)
        right = np.zeros(nr)
        if u_now > 0:  # flow enters at z_min (bladder end)
            left[lumen] = Tin
            right = T[:, -1]
        elif u_now < 0:
            right[lumen] = Tin
            left = T[:, 0]
        Tp = np.concatenate([left[:, None], T, right[:, None]], axis=1)
        lap_z = k * (Tp[:, 2:] - 2 * T + Tp[:, :-2]) / dz**2

        # first-order upwind advection, lumen only
        u = (u_now * profile)[:, None]
        if u_now >= 0:
            adv = -u * (T - Tp[:, :-2]) / dz
        else:
            adv = -u * (Tp[:, 2:] - T) / dz

        rhs = (div_r + lap_z - W * T) / rho_c + adv
        if source is not None:
            Q, t_on, t_off = source
            if t_on <= t < t_off:
                rhs += Q / rho_c
        T = T + dt * rhs
        peak_T = max(peak_T, T.max())
        cem43 += dt / 60.0 * np.where(T >= 6, 0.5, 0.25) ** (43 - (37 + T))  # Sapareto-Dewey

    return dict(t=np.array(times), samples={k_: np.array(v) for k_, v in samples.items()},
                T=T, r=r, z=z, peak=peak_T, cem43_max=cem43.max())


def voxel_mean(z_center, half_len=1.0e-3, r_lim=2.0e-3):
    """Mean temperature in a ~2x2x2 mm thermometry voxel centred on the ureter."""
    def fn(T, r, z):
        rm = r < r_lim
        zm = np.abs(z - z_center) <= half_len
        w = r[rm][:, None] * np.ones(zm.sum())[None, :]
        return float((T[np.ix_(rm, zm)] * w).sum() / w.sum())
    return fn


# =============================================================== Experiment A
def experiment_a(geo=Ureter()):
    """Heat a 1.5-mm focal spot for 5 s, read voxels 10 mm kidney-side and bladder-side."""
    r, z, _, _ = build_grid(geo, -40e-3, 40e-3)
    sigma = 1.5e-3
    Q_unit = 1e6 * np.exp(-(r[:, None] ** 2 + z[None, :] ** 2) / (2 * sigma**2))
    sensors = {"kidney": voxel_mean(+10e-3), "bladder": voxel_mean(-10e-3), "focus": voxel_mean(0.0)}

    # Calibrate power so the focal voxel peaks at +2 K with no flow (sub-hyperthermic).
    cal = simulate(geo, 0.0, 30.0, source=(Q_unit, 0.0, 5.0), record=sensors)
    scale = 2.0 / cal["samples"]["focus"].max()
    Q = Q_unit * scale

    velocities_cm = [-5, -3, -2, -1, -0.5, -0.25, -0.13, 0, 0.13, 0.25, 0.5, 1, 2, 3, 5]
    runs = {}
    for v in velocities_cm:
        res = simulate(geo, v / 100, 30.0, source=(Q, 0.0, 5.0), record=sensors)
        runs[v] = res
        print(f"  A: U={v:+5.2f} cm/s  peak={res['peak']:.2f} K  "
              f"kidney max={res['samples']['kidney'].max():.3f}  "
              f"bladder max={res['samples']['bladder'].max():.3f}")

    # A short reflux jet during voiding: 2 s at +3 cm/s, starting while the spot is hot.
    pulse = lambda t: 0.03 if 4.0 <= t < 6.0 else 0.0
    runs["pulse"] = simulate(geo, pulse, 30.0, source=(Q, 0.0, 5.0), record=sensors)

    # Direction statistic: D = mean(kidney) - mean(bladder) over the frames where a
    # flow signal can exist (1-7 s: heating on + wash-out), sampled at 1 Hz. With
    # independent Gaussian noise sigma per frame, sd(D) = sigma*sqrt(2/N).
    # The system is linear, so a stronger pulse just rescales D. Two powers:
    #   2 K focal-voxel rise (as simulated) and 6 K (x3; see max_CEM43_min_6K below).
    frame_idx = np.arange(10, 71, 10)
    N = len(frame_idx)
    noise_levels = [0.2, 0.5]
    gains = {"2K": 1.0, "6K": 3.0}
    detect = {}
    for g_name, g in gains.items():
        for s in noise_levels:
            sd = s * np.sqrt(2 / N)
            row = []
            for v in velocities_cm:
                smp = runs[v]["samples"]
                D = g * (smp["kidney"][frame_idx] - smp["bladder"][frame_idx]).mean()
                # one-sided test at 5 % false-positive rate per direction
                row.append(float(norm.cdf(abs(D) / sd - norm.ppf(0.95))) if v != 0 else 0.05)
            detect[(g_name, s)] = row

    plot_a(runs, velocities_cm, detect, geo)
    return dict(
        power_density_peak_W_per_cm3=float(Q.max() / 1e6),
        velocities_cm_s=velocities_cm,
        focal_peak_K={str(v): float(runs[v]["peak"]) for v in velocities_cm},
        kidney_peak_K={str(v): float(runs[v]["samples"]["kidney"].max()) for v in velocities_cm},
        bladder_peak_K={str(v): float(runs[v]["samples"]["bladder"].max()) for v in velocities_cm},
        max_CEM43_min=float(max(runs[v]["cem43_max"] for v in velocities_cm)),
        max_CEM43_min_6K=float(simulate(geo, 0.0, 30.0, source=(3 * Q, 0.0, 5.0))["cem43_max"]),
        p_correct_direction={f"{g} focal, sigma={s} K": dict(zip(map(str, velocities_cm), row))
                             for (g, s), row in detect.items()},
        pulse_kidney_peak_K=float(runs["pulse"]["samples"]["kidney"].max()),
        pulse_bladder_peak_K=float(runs["pulse"]["samples"]["bladder"].max()),
    )


def plot_a(runs, velocities_cm, detect, geo):
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5))
    cases = [(-2, "Antegrade 2 cm/s (normal peristalsis)"), (0, "No flow"),
             (2, "Retrograde 2 cm/s (reflux)")]
    for ax, (v, title) in zip(axes[0], cases):
        res = runs[v]
        ax.plot(res["t"], res["samples"]["focus"], color="0.55", lw=1.2, label="heated spot")
        ax.plot(res["t"], res["samples"]["kidney"], color="#c0392b", lw=2, label="voxel 10 mm kidney-side")
        ax.plot(res["t"], res["samples"]["bladder"], color="#2471a3", lw=2, label="voxel 10 mm bladder-side")
        ax.axvspan(0, 5, color="orange", alpha=0.12)
        ax.set_title(title)
        ax.set_xlabel("time [s]")
        ax.set_ylabel("ΔT [K]")
        ax.set_ylim(-0.05, 2.1)
    axes[0, 0].legend(fontsize=8, loc="upper right")

    # temperature field snapshots (mirror r to show the full ureter)
    ax = axes[1, 0]
    res = runs[2]
    T = res["T"]
    full = np.vstack([T[::-1], T])
    rr = np.concatenate([-res["r"][::-1], res["r"]]) * 1e3
    im = ax.pcolormesh(res["z"] * 1e3, rr, full, cmap="inferno", shading="auto")
    ax.axhline(geo.radius * 1e3, color="w", lw=0.6, ls=":")
    ax.axhline(-geo.radius * 1e3, color="w", lw=0.6, ls=":")
    ax.set_title("Field at t = 30 s, reflux 2 cm/s")
    ax.set_xlabel("z [mm]  (bladder ←   → kidney)")
    ax.set_ylabel("r [mm]")
    ax.set_ylim(-8, 8)
    fig.colorbar(im, ax=ax, label="ΔT [K]")

    ax = axes[1, 1]
    vk = [runs[v]["samples"]["kidney"].max() for v in velocities_cm]
    vb = [runs[v]["samples"]["bladder"].max() for v in velocities_cm]
    vf = [runs[v]["peak"] for v in velocities_cm]
    ax.plot(velocities_cm, vk, "o-", color="#c0392b", label="kidney-side voxel peak")
    ax.plot(velocities_cm, vb, "o-", color="#2471a3", label="bladder-side voxel peak")
    ax.plot(velocities_cm, vf, "s:", color="0.4", label="hottest point anywhere")
    ax.axvline(0, color="k", lw=0.5)
    ax.set_xlabel("mean urine velocity [cm/s]   (− antegrade, + reflux)")
    ax.set_ylabel("peak ΔT [K]")
    ax.set_title("Asymmetry and convective wash-out")
    ax.legend(fontsize=8)

    ax = axes[1, 2]
    styles = {("6K", 0.2): ("#1b5e20", "-"), ("6K", 0.5): ("#43a047", "-"),
              ("2K", 0.2): ("#e65100", "--"), ("2K", 0.5): ("#f9a825", "--")}
    for key, (c, ls) in styles.items():
        ax.plot(velocities_cm, detect[key], "o", ls=ls, color=c,
                label=f"+{key[0][0]} K pulse, σ = {key[1]} K/frame")
    ax.axhline(0.95, color="k", ls=":", lw=0.8)
    ax.set_xscale("symlog", linthresh=0.1)
    ax.set_xlabel("mean urine velocity [cm/s]")
    ax.set_ylabel("P(correct direction call)")
    ax.set_title("Direction detectability, 7 frames @ 1 Hz")
    ax.legend(fontsize=8)
    fig.suptitle("A. Thermal time-of-flight: 5 s focal heating (+2 K) of a 2-mm-radius ureter", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "fig_a_time_of_flight.png", dpi=130)
    plt.close(fig)

    # pulse case separately
    res = runs["pulse"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(res["t"], res["samples"]["focus"], color="0.55", label="heated spot")
    ax.plot(res["t"], res["samples"]["kidney"], color="#c0392b", lw=2, label="kidney-side voxel")
    ax.plot(res["t"], res["samples"]["bladder"], color="#2471a3", lw=2, label="bladder-side voxel")
    ax.axvspan(0, 5, color="orange", alpha=0.12, label="heating on")
    ax.axvspan(4, 6, color="purple", alpha=0.12, label="reflux jet 3 cm/s")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("ΔT [K]")
    ax.set_title("A'. Transient reflux jet during voiding (2 s, ≈0.75 mL)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_a_pulse.png", dpi=130)
    plt.close(fig)


# =============================================================== Experiment B
def transit_retention(geo: Ureter, length=0.12, velocity=0.03, duration=4.0):
    """Warm urine (+1 K) refluxes from the bladder end up a ureter of given length.
    Returns the bulk (flow-weighted) temperature arriving at the renal-pelvis end."""
    def bulk_at_outlet(T, r, z):
        rm = r < geo.radius
        w = r[rm] * (1 - (r[rm] / geo.radius) ** 2)
        return float((T[rm, -3] * w).sum() / w.sum())

    vel = lambda t: velocity if t < duration else 0.0
    res = simulate(geo, vel, duration + 2.0, z_range=(0.0, length),
                   inlet_temp=lambda t: 1.0, record={"outlet": bulk_at_outlet})
    arrived = res["samples"]["outlet"]
    t = res["t"]
    vol = np.pi * geo.radius**2 * velocity * duration * 1e6
    # retention = mean ΔT of the fluid that actually made it to the pelvis while flowing
    mask = (t > length / velocity) & (t <= duration)
    retention = float(arrived[mask].mean()) if mask.any() else 0.0
    return dict(t=t, outlet=arrived, retention=retention, volume_mL=vol)


def pelvis_decay(volume_mL, t_end=120.0, perf=0.005):
    """Refluxed fluid pooled in the renal pelvis, idealised as a sphere of urine in
    renal-sinus tissue (Pennes, 1-D spherical). Returns time course of the mean ΔT
    of the fluid, for an initial +1 K."""
    a = (3 * volume_mL * 1e-6 / (4 * np.pi)) ** (1 / 3)
    R = a + 25e-3
    dr = 0.25e-3
    r = (np.arange(int(R / dr)) + 0.5) * dr
    fluid = r < a
    k = np.where(fluid, URINE["k"], TISSUE["k"])
    rho_c = np.where(fluid, URINE["rho_c"], 1050 * 3600)
    W = np.where(fluid, 0.0, perf * RHO_C_BLOOD)
    T = np.where(fluid, 1.0, 0.0)
    dt = 0.2 * dr**2 / (k / rho_c).max()
    n = int(t_end / dt)
    rf = r[:-1] + dr / 2
    kf = 0.5 * (k[1:] + k[:-1])
    vol_w = r[fluid] ** 2
    times, mean_T = [], []
    every = max(1, int(1.0 / dt))
    for i in range(n + 1):
        if i % every == 0:
            times.append(i * dt)
            mean_T.append(float((T[fluid] * vol_w).sum() / vol_w.sum()))
        F = rf**2 * kf * (T[1:] - T[:-1]) / dr
        div = np.zeros_like(T)
        div[:-1] += F
        div[1:] -= F
        div /= r**2 * dr
        T = T + dt * (div - W * T) / rho_c
        T[-1] = 0.0
    return dict(t=np.array(times), mean=np.array(mean_T), radius_mm=a * 1e3)


def experiment_b():
    print("  B: transit through ureter …")
    transit = {}
    for label, geo in (("normal (r=2 mm)", Ureter(radius=2e-3)),
                       ("dilated (r=4 mm, grade IV)", Ureter(radius=4e-3, dr=0.25e-3, dz=0.5e-3, r_max=14e-3))):
        for v in (0.02, 0.05):
            res = transit_retention(geo, velocity=v, duration=12e-2 / v + 2.0)
            transit[(label, v)] = res
            print(f"     {label:28s} U={v*100:.0f} cm/s  retention={res['retention']:.2f}  "
                  f"V={res['volume_mL']:.2f} mL")

    print("  B: decay in renal pelvis …")
    decay = {v: pelvis_decay(v) for v in (0.5, 1.0, 2.0, 5.0)}
    for v, d in decay.items():
        print(f"     V={v} mL (a={d['radius_mm']:.1f} mm): mean ΔT at 30 s = {np.interp(30, d['t'], d['mean']):.2f}")

    # Detection: instillate offset needed for a 3-sigma detection 15 s after reflux ends.
    # MR thermometry (PRF shift): ~0.5 K per 2.5-mm voxel at ~1 s/frame, averaging a
    # region of n voxels inside the pelvis improves it by sqrt(n).
    # Microwave radiometry (1-4 GHz): ~0.1 K, but the antenna averages a ~30 mL volume,
    # so the signal is diluted by V_reflux/30 (partial volume).
    vols = np.linspace(0.25, 6, 60)
    ret_normal = transit[("normal (r=2 mm)", 0.05)]["retention"]
    def residual(v):
        d = pelvis_decay(v, t_end=30)
        return np.interp(15, d["t"], d["mean"])
    res_curve = np.array([residual(v) for v in np.linspace(0.25, 6, 12)])
    res_interp = np.interp(vols, np.linspace(0.25, 6, 12), res_curve)
    gain = ret_normal * res_interp                                  # ΔT_pelvis / ΔT_instillate
    voxel = 2.5e-3 ** 3 * 1e6                                       # mL per voxel
    n_vox = np.maximum(1, vols / voxel * 0.5)                       # half the pool usable
    mr_sigma = 0.5 / np.sqrt(n_vox) * np.sqrt(2)                    # pre/post difference
    mr_needed = 3 * mr_sigma / gain
    rad_needed = 3 * 0.1 * np.sqrt(2) / (gain * np.minimum(1, vols / 30))

    plot_b(transit, decay, vols, mr_needed, rad_needed)
    return dict(
        transit_retention={f"{k[0]} @ {k[1]*100:.0f} cm/s": v["retention"] for k, v in transit.items()},
        pelvis_mean_dT_at_15s_per_K={str(v): float(np.interp(15, d["t"], d["mean"])) for v, d in decay.items()},
        pelvis_mean_dT_at_60s_per_K={str(v): float(np.interp(60, d["t"], d["mean"])) for v, d in decay.items()},
        instillate_offset_needed_K={
            "reflux_mL": [0.5, 1, 2, 5],
            "MR_thermometry": [float(np.interp(x, vols, mr_needed)) for x in (0.5, 1, 2, 5)],
            "microwave_radiometry": [float(np.interp(x, vols, rad_needed)) for x in (0.5, 1, 2, 5)],
        },
    )


def plot_b(transit, decay, vols, mr_needed, rad_needed):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    ax = axes[0]
    for (label, v), res in transit.items():
        ls = "-" if v == 0.05 else "--"
        c = "#6a1b9a" if "dilated" in label else "#00838f"
        ax.plot(res["t"], res["outlet"], ls=ls, color=c, label=f"{label}, {v*100:.0f} cm/s")
    ax.set_xlabel("time since reflux starts [s]")
    ax.set_ylabel("ΔT arriving at pelvis / ΔT instillate")
    ax.set_title("Heat survives the 12-cm trip up the ureter")
    ax.legend(fontsize=7.5)
    ax.set_ylim(0, 1.05)

    ax = axes[1]
    for v, d in decay.items():
        ax.plot(d["t"], d["mean"], label=f"{v} mL refluxed (sphere r={d['radius_mm']:.1f} mm)")
    ax.set_xlabel("time after reflux arrives [s]")
    ax.set_ylabel("mean ΔT of pooled urine (fraction)")
    ax.set_title("Signal decay in the renal pelvis")
    ax.legend(fontsize=8)

    ax = axes[2]
    ax.plot(vols, mr_needed, color="#c62828", lw=2, label="MR thermometry (PRF, 0.5 K/voxel)")
    ax.plot(vols, rad_needed, color="#1565c0", lw=2, label="Microwave radiometry (0.1 K, ~30 mL view)")
    ax.axhspan(0, 4, color="green", alpha=0.08)
    ax.axhline(4, color="green", ls=":", lw=1)
    ax.text(5.9, 4.2, "≈ comfortable range for warmed (≤41 °C)\nor cooled saline", ha="right",
            va="bottom", fontsize=8, color="green")
    ax.set_yscale("log")
    ax.set_xlabel("refluxed volume [mL]")
    ax.set_ylabel("|instillate − body| needed for 3σ [K]")
    ax.set_title("How warm/cold must the bladder fill be?")
    ax.legend(fontsize=8, loc="upper right")
    fig.suptitle("B. Thermal VCUG: off-temperature bladder fill as a reflux tracer", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "fig_b_thermal_vcug.png", dpi=130)
    plt.close(fig)


def scales():
    """Back-of-envelope dimensionless numbers that drive everything."""
    R, L = 2e-3, 10e-3
    out = {}
    for name, u in (("mean urine production (1 mL/min)", 1.67e-8 / (np.pi * R**2)),
                    ("peristaltic bolus", 0.025), ("voiding reflux jet", 0.05)):
        out[name] = dict(u_cm_s=u * 100, Peclet_axial=u * L / ALPHA_URINE,
                         Graetz_like_t_cross_over_t_diff=(L / u) / (R**2 / (5.78 * ALPHA_URINE)))
    out["radial_diffusion_time_s"] = R**2 / (5.78 * ALPHA_URINE)
    out["perfusion_time_constant_tissue_s"] = TISSUE["rho_c"] / (TISSUE["perf"] * RHO_C_BLOOD)
    return out


if __name__ == "__main__":
    results = {"scales": scales()}
    print("Experiment A …")
    results["A_time_of_flight"] = experiment_a()
    print("Experiment B …")
    results["B_thermal_vcug"] = experiment_b()
    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    print("wrote", OUT / "results.json")
