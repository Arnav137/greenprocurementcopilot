"""
Step 2: calculate emissions from structured.json.
This script does not call the LLM. It uses deterministic arithmetic.

Run after structure.py:
    python calculate.py
"""
import json
import re

INPUT_FILE = "structured.json"

def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def calculate(data):
    material = (data.get("material") or "").lower()
    process = (data.get("process") or "").lower()
    clinker = data.get("clinker_tonnes")
    factor = data.get("emission_factor")
    factor_unit = re.sub(r"\s+", " ", (data.get("emission_factor_unit") or "").strip().lower())
    source = data.get("factor_source") or "Not supplied"

    # Cement clinker calcination
    if is_number(clinker) and (
        "cement" in material or "clinker" in material or "calcination" in process
    ):
        if clinker < 0:
            return {"status": "INVALID", "error": "Clinker quantity cannot be negative."}
        if is_number(factor):
            accepted = {
                "kg co2 per tonne clinker", "kg co2/tonne clinker",
                "kg co2e per tonne clinker", "kg co2e/tonne clinker"
            }
            if factor_unit not in accepted:
                return {
                    "status": "REVIEW",
                    "error": "Custom clinker factor must be in kg CO2 (or CO2e) per tonne clinker.",
                    "structured_values": data
                }
            used_factor = float(factor)
            used_source = source
            is_default = False
        else:
            used_factor = 525.0
            used_source = "Cement protocol default (525 kg CO2/tonne clinker; verify applicability)"
            is_default = True

        emissions = float(clinker) * used_factor
        return {
            "status": "CALCULATED_REVIEW" if is_default else "CALCULATED",
            "material": data.get("material"),
            "process": "Clinker calcination only",
            "activity_quantity": float(clinker),
            "activity_unit": "tonnes clinker",
            "emission_factor": used_factor,
            "emission_factor_unit": "kg CO2 per tonne clinker",
            "factor_source": used_source,
            "factor_is_default": is_default,
            "emissions_kg_co2": emissions,
            "emissions_tonnes_co2": emissions / 1000,
            "boundary": data.get("boundary") or "Calcination only",
            "warnings": [
                "Calcination only: excludes kiln fuel, electricity, transport and other sources.",
                *(
                    ["Default factor used; label as an estimate and verify source/version."]
                    if is_default else []
                )
            ],
        }

    # Generic activity × explicit factor, for steel/fuel/process records
    activity = data.get("fuel_quantity")
    activity_unit = data.get("fuel_unit")
    activity_name = data.get("fuel_name") or data.get("process") or data.get("material")
    if not is_number(activity):
        activity = data.get("quantity")
        activity_unit = data.get("unit")
    if not is_number(activity):
        return {
            "status": "NEEDS_DATA",
            "error": "No supported numeric activity found. Provide clinker tonnes or an activity quantity with unit.",
            "structured_values": data
        }
    if activity < 0:
        return {"status": "INVALID", "error": "Activity quantity cannot be negative."}
    if not is_number(factor):
        return {
            "status": "NEEDS_FACTOR",
            "error": "No explicit emission factor was found. Add a verified factor for this process and unit; the calculator will not guess.",
            "structured_values": data
        }
    if not isinstance(activity_unit, str) or not activity_unit.strip():
        return {"status": "NEEDS_DATA", "error": "Activity unit is missing."}

    norm_unit = re.sub(r"\s+", " ", activity_unit.strip().lower())
    accepted = {
        f"kg co2 per {norm_unit}", f"kg co2/{norm_unit}",
        f"kg co2e per {norm_unit}", f"kg co2e/{norm_unit}"
    }
    if factor_unit not in accepted:
        return {
            "status": "REVIEW",
            "error": f"Factor unit '{data.get('emission_factor_unit')}' does not match activity unit '{activity_unit}'. No conversion is performed.",
            "structured_values": data
        }
    emissions = float(activity) * float(factor)
    return {
        "status": "CALCULATED",
        "material": data.get("material"),
        "process": activity_name,
        "activity_quantity": float(activity),
        "activity_unit": activity_unit,
        "emission_factor": float(factor),
        "emission_factor_unit": data.get("emission_factor_unit"),
        "factor_source": source,
        "factor_is_default": False,
        "emissions_kg_co2": emissions,
        "emissions_tonnes_co2": emissions / 1000,
        "boundary": data.get("boundary"),
        "warnings": [
            "Confirm that the factor is authoritative and suitable for this exact process and calculation boundary."
        ],
    }

def main():
    try:
        with open(INPUT_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("structured.json not found. Run python structure.py first.")
        return
    except json.JSONDecodeError as e:
        print(f"structured.json is invalid JSON: {e}")
        return

    result = calculate(data)
    print("CARBON CALCULATION RESULT:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    with open("calculation_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("\nSaved calculation_result.json")

if __name__ == "__main__":
    main()
