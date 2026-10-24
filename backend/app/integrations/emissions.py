def calculate_co2e(factor_kg_per_inr: float, amount_inr: float,
                   classification_confidence: float = 1.0) -> dict:
    """Spend-based estimate: spend x factor. Returns co2e + method + confidence + flags."""
    co2e = (amount_inr or 0) * (factor_kg_per_inr or 0)
    flags = ["spend-based estimate (less precise than activity-based)"]
    if classification_confidence < 0.8:
        flags.append("low classification confidence")
        confidence = "low"
    else:
        confidence = "medium"
    return {"co2e_kg": round(co2e, 1), "method": "spend", "confidence": confidence, "data_flags": flags}
