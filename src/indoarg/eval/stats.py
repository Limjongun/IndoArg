"""Statistical inference: paired pair_id bootstrap CI, McNemar + Holm, and Exp B GEE."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests


def paired_bootstrap_ci(
    pair_scores: dict[str, list[float]],
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, float]:
    """Bootstrap 95% CI resampling at pair_id level so all variants move together."""
    pair_ids = sorted(pair_scores.keys())
    if not pair_ids:
        return {"mean": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}

    pair_means = np.array([float(np.mean(pair_scores[pid])) for pid in pair_ids], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pair_means), size=(n_resamples, len(pair_means)))
    boot_means = pair_means[idx].mean(axis=1)
    lo = float(np.percentile(boot_means, 100.0 * (alpha / 2.0)))
    hi = float(np.percentile(boot_means, 100.0 * (1.0 - alpha / 2.0)))
    return {
        "mean": round(float(pair_means.mean()), 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
    }


def paired_register_gap_ci(
    pair_reg_scores: dict[str, dict[str, int]],
    reg_a: str = "formal",
    reg_b: str = "informal",
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, float]:
    """Paired bootstrap CI for DeltaReg = EXA(reg_a) - EXA(reg_b) over matched pairs."""
    diffs = np.array(
        [
            float(scores[reg_a] - scores[reg_b])
            for pid, scores in sorted(pair_reg_scores.items())
            if reg_a in scores and reg_b in scores
        ],
        dtype=float,
    )
    if len(diffs) == 0:
        return {"delta": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "n_pairs": 0}

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diffs), size=(n_resamples, len(diffs)))
    boot = diffs[idx].mean(axis=1)
    lo = float(np.percentile(boot, 100.0 * (alpha / 2.0)))
    hi = float(np.percentile(boot, 100.0 * (1.0 - alpha / 2.0)))
    return {
        "delta": round(float(diffs.mean()), 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
        "n_pairs": int(len(diffs)),
    }


def mcnemar_test(a_correct: list[int], b_correct: list[int]) -> dict[str, Any]:
    """Paired McNemar test on binary outcomes for two strategies or registers."""
    if len(a_correct) != len(b_correct):
        raise ValueError("Panjang vektor a_correct dan b_correct harus sama.")
    n11 = sum(1 for a, b in zip(a_correct, b_correct, strict=True) if a == 1 and b == 1)
    n10 = sum(1 for a, b in zip(a_correct, b_correct, strict=True) if a == 1 and b == 0)
    n01 = sum(1 for a, b in zip(a_correct, b_correct, strict=True) if a == 0 and b == 1)
    n00 = sum(1 for a, b in zip(a_correct, b_correct, strict=True) if a == 0 and b == 0)
    table = [[n11, n10], [n01, n00]]
    use_exact = (n10 + n01) < 25
    res = mcnemar(table, exact=use_exact, correction=not use_exact)
    return {
        "n11": n11,
        "n10": n10,
        "n01": n01,
        "n00": n00,
        "exact": use_exact,
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
    }


def holm_correction(p_values: list[float], alpha: float = 0.05) -> dict[str, Any]:
    """Apply Holm-Bonferroni correction for multiple comparisons."""
    if not p_values:
        return {"reject": [], "p_adjusted": []}
    reject, p_adj, _, _ = multipletests(p_values, alpha=alpha, method="holm")
    return {
        "reject": [bool(x) for x in reject],
        "p_adjusted": [float(x) for x in p_adj],
    }


def baseline_floor_check(bf16_exa: float, threshold: float = 0.20) -> dict[str, Any]:
    """Verify BF16 EXA >= 20% before interpreting quantization degradation (§12.2)."""
    passed = bf16_exa >= threshold
    return {
        "bf16_exa": round(float(bf16_exa), 4),
        "threshold": threshold,
        "passed": passed,
        "note": (
            "Lulus ambang baseline BF16."
            if passed
            else "PERINGATAN: EXA BF16 < 20%; jangan tafsirkan penurunan kuantisasi."
        ),
    }


def quant_register_interaction_gee(df: pd.DataFrame) -> dict[str, Any]:
    """Fit Binomial GEE for EXA ~ C(register) * quant_bits clustered by pair_id (Exp B)."""
    required = {"pair_id", "register", "quant_bits", "exa"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Kolom wajib hilang untuk GEE Eksp. B: {sorted(missing)}")

    work = df.copy()
    work["exa"] = work["exa"].astype(float)
    work["quant_bits"] = work["quant_bits"].astype(float)

    model = smf.gee(
        "exa ~ C(register, Treatment(reference='formal')) * quant_bits",
        groups="pair_id",
        data=work,
        family=sm.families.Binomial(),
    )
    res = model.fit()
    return {
        "params": {k: round(float(v), 6) for k, v in res.params.items()},
        "p_values": {k: round(float(v), 6) for k, v in res.pvalues.items()},
        "n_obs": int(res.nobs),
    }
