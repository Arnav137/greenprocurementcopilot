def compute_scenario(base_co2e: float, base_spend: float, co2e_ratio: float,
                     price_delta_pct: float, share: float) -> dict:
    """Shift `share` (0-1) of volume to an alternative.
    Emissions blend linearly; cost delta is the share-weighted price difference."""
    share = max(0.0, min(1.0, share))
    new_co2e = base_co2e * (1 - share) + base_co2e * co2e_ratio * share
    cost_delta_pct = share * price_delta_pct
    return {
        "volume_share": share,
        "baseline_co2e_kg": round(base_co2e, 1),
        "new_co2e_kg": round(new_co2e, 1),
        "co2e_saved_kg": round(base_co2e - new_co2e, 1),
        "reduction_pct": round((base_co2e - new_co2e) / base_co2e * 100, 1) if base_co2e else 0,
        "cost_delta_pct": round(cost_delta_pct, 2),
        "cost_delta_inr": round(base_spend * cost_delta_pct / 100, 2),
    }
