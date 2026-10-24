"""Validate extracted procurement/emissions data before calculation.

Statuses:
- VALID: structurally usable; still not a guarantee that the factor is authoritative.
- REVIEW: no hard contradiction, but missing evidence or ambiguity needs human review.
- INVALID: malformed or physically impossible input; do not calculate.
"""
import json
import math
import re
from pathlib import Path

INPUT_FILE = Path("structured.json")
OUTPUT_FILE = Path("validation_result.json")

NUMERIC_FIELDS = ("quantity", "clinker_tonnes", "fuel_quantity", "emission_factor", "factor_year")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def norm(value):
    return re.sub(r"\s+", " ", value.strip().lower()) if isinstance(value, str) else ""


def validate(data):
    errors, warnings, checks = [], [], []
    if not isinstance(data, dict):
        return {"status": "INVALID", "errors": ["Top-level JSON must be an object/dictionary."], "warnings": [], "checks": []}

    checks.append("Top-level JSON is an object")
    for field in NUMERIC_FIELDS:
        value = data.get(field)
        if value is not None and not is_number(value):
            errors.append(f"'{field}' must be a finite number or null.")
        elif is_number(value) and field != "factor_year" and value < 0:
            errors.append(f"'{field}' cannot be negative.")
    if data.get("factor_year") is not None and is_number(data.get("factor_year")):
        year = data["factor_year"]
        if not 1900 <= year <= 2100:
            warnings.append("factor_year is outside the expected range 1900–2100; verify it.")

    material = norm(data.get("material"))
    process = norm(data.get("process"))
    unit = norm(data.get("unit"))
    clinker = data.get("clinker_tonnes")
    quantity = data.get("quantity")
    fuel_quantity = data.get("fuel_quantity")
    factor = data.get("emission_factor")
    factor_unit = norm(data.get("emission_factor_unit"))

    if not material and not process:
        warnings.append("Both material and process are missing; identify what the activity represents.")
    else:
        checks.append("Material or process is identified")

    has_activity = (is_number(clinker) and clinker >= 0) or (is_number(fuel_quantity) and fuel_quantity >= 0) or (is_number(quantity) and quantity >= 0)
    if not has_activity:
        warnings.append("No usable non-negative activity quantity was found.")
    else:
        checks.append("A numeric activity quantity is available")

    if is_number(clinker) and clinker >= 0 and not unit:
        # clinker_tonnes is explicitly expressed in tonnes by the field name
        checks.append("clinker_tonnes field explicitly represents tonnes")
    elif has_activity and not (isinstance(data.get("fuel_unit"), str) and data.get("fuel_unit").strip()) and not unit:
        warnings.append("Activity unit is missing; the quantity cannot be interpreted reliably.")

    if factor is None:
        if is_number(clinker) and clinker >= 0 and ("cement" in material or "clinker" in material or "calcination" in process):
            warnings.append("No explicit factor supplied. The calculator may use its 525 kg CO2/tonne clinker default; verify applicability and label as an estimate.")
        else:
            warnings.append("Emission factor is missing. Do not calculate emissions until a suitable factor is supplied.")
    elif is_number(factor):
        if not factor_unit:
            warnings.append("Emission factor unit is missing.")
        else:
            checks.append("Emission factor has a unit")
        if not (isinstance(data.get("factor_source"), str) and data["factor_source"].strip()):
            warnings.append("Factor source is missing; the factor is not traceable.")
        else:
            checks.append("Factor source is recorded")

        # Validate recognized unit patterns for generic activity records. No unit conversion is attempted.
        activity_unit = norm(data.get("fuel_unit") or data.get("unit"))
        if activity_unit and factor_unit:
            accepted = {f"kg co2 per {activity_unit}", f"kg co2/{activity_unit}",
                        f"kg co2e per {activity_unit}", f"kg co2e/{activity_unit}"}
            is_clinker = is_number(clinker) and ("clinker" in material or "cement" in material or "calcination" in process)
            clinker_units = {"kg co2 per tonne clinker", "kg co2/tonne clinker",
                             "kg co2e per tonne clinker", "kg co2e/tonne clinker"}
            if is_clinker and factor_unit not in clinker_units:
                warnings.append("Factor unit is not a recognized clinker-specific unit; check that it is kg CO2(e) per tonne clinker.")
            elif not is_clinker and factor_unit not in accepted:
                warnings.append("Factor unit does not match the activity unit using the supported exact formats. No unit conversion is performed.")
            else:
                checks.append("Factor unit appears compatible with activity unit")

    for field, label in (("factor_year", "Factor year"), ("geography", "Geography"),
                         ("calculation_method", "Calculation method"), ("boundary", "Calculation boundary")):
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            warnings.append(f"{label} is missing; record it if available for auditability.")
        else:
            checks.append(f"{label} is recorded")

    raw_input = data.get("_raw_input")
    if isinstance(raw_input, str) and raw_input.strip():
        # Current structuring schema emits one object. Multiple purchase lines may need separate records.
        if len(re.findall(r"(?im)^\s*(?:vendor|supplier|item|material)\s*:", raw_input)) > 1:
            warnings.append("Input appears to contain multiple purchase records, but this schema validates one record at a time. Split records before calculating supplier-level results.")

    status = "INVALID" if errors else ("REVIEW" if warnings else "VALID")
    return {"status": status, "errors": errors, "warnings": warnings, "checks": checks}


def main():
    try:
        with INPUT_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("structured.json not found. Run python structure.py first.")
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        result = {"status": "INVALID", "errors": [f"structured.json is invalid JSON: {exc}"], "warnings": [], "checks": []}
        OUTPUT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        raise SystemExit(2)

    result = validate(data)
    OUTPUT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("VALIDATION RESULT:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nSaved {OUTPUT_FILE}")
    if result["status"] == "INVALID":
        print("Validation failed. Calculation will not run.")
        raise SystemExit(2)
    if result["status"] == "REVIEW":
        print("Review required. Pipeline will continue, but check the warnings before using the result.")

if __name__ == "__main__":
    main()
