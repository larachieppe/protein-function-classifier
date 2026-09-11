"""Draw Conditions from the literature registry.

Every scenario names its own background level and access route explicitly.  There is no
default "typical case": a point scenario exists only so the report can show how far a
single-number answer sits from the interval.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import literature as lit
from .mechanisms import Conditions
from .uncertain import Shape

ROUTES = {
    "distal_uvj": ("Anterior suprapubic -> distal ureter / UVJ", lit.DEPTH_DISTAL),
    "proximal": ("Posterior or flank -> proximal ureter / renal pelvis", lit.DEPTH_PROXIMAL),
    "mid": ("Any -> mid ureter (usually gas-obscured)", lit.DEPTH_MID),
}

BACKGROUNDS = {
    "favourable": lit.BG_FAVOURABLE,
    "middle": lit.BG_MIDDLE,
    "worst": lit.BG_WORST,
}


@dataclass(frozen=True)
class Scenario:
    route: str
    background: str
    f0_hz: float
    frac_bw: float
    dsg: float
    aperture_m: float
    profile_shape: str = "tanh"
    mix_spectrum: str = "kolmogorov"
    clutter_suppression_db: float = 0.0
    n: int = 20000
    seed: int = 20260910

    def draw(self) -> Conditions:
        rng = np.random.default_rng(self.seed)
        n = self.n
        _, depth_q = ROUTES[self.route]
        bg_q = BACKGROUNDS[self.background]

        c_urine = lit.C_URINE.sample(rng, n)
        rho_urine = lit.RHO_URINE.sample(rng, n)
        return Conditions(
            f0=np.full(n, self.f0_hz),
            bandwidth=np.full(n, self.f0_hz * self.frac_bw),
            c_tissue=lit.C_TISSUE.sample(rng, n),
            c_urine=c_urine,
            rho_urine=rho_urine,
            # Z in MRayl, consistent with the registry entries
            z_urine=rho_urine * c_urine / 1e6,
            z_wall=lit.Z_URETER_WALL.sample(rng, n),
            dc_drho=lit.DC_DRHO.sample(rng, n),
            alpha=lit.ALPHA_TISSUE.sample(rng, n),
            depth=depth_q.sample(rng, n),
            aperture=np.full(n, self.aperture_m),
            dsg=np.full(n, self.dsg),
            edge_width=lit.EDGE_WIDTH.sample(rng, n),
            sharp_fraction=lit.SHARP_FRACTION.sample(rng, n),
            bsc_urine=lit.BSC_URINE.sample(rng, n),
            mix_corr_length=lit.MIX_CORR_LENGTH.sample(rng, n),
            mix_z_variance=lit.MIX_Z_VARIANCE.sample(rng, n),
            lumen_open=lit.LUMEN_OPEN.sample(rng, n),
            lumen_collapsed=lit.LUMEN_COLLAPSED.sample(rng, n),
            background_db=np.full(n, bg_q.nom),
            profile_shape=self.profile_shape,
            mix_spectrum=self.mix_spectrum,
            clutter_suppression_db=self.clutter_suppression_db,
        )


def favourable_controlled_geometry(dsg: float | None = None, **kw) -> Scenario:
    """The configuration in which a failure legitimately closes a mechanism.

    Shallowest declared depth, favourable background, best-case profile assumptions.
    Defined explicitly so that "we tried hard" is a specification rather than a claim.
    """
    return Scenario(
        route=kw.pop("route", "distal_uvj"),
        background="favourable",
        f0_hz=kw.pop("f0_hz", 5e6),
        frac_bw=kw.pop("frac_bw", 0.6),
        dsg=lit.DSG_MAX.nom if dsg is None else dsg,
        aperture_m=kw.pop("aperture_m", lit.ELEMENT_DIAMETER.nom),
        **kw,
    )
