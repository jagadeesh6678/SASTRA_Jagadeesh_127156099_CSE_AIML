"""
Deterministic ASIL computation based on ISO 26262-3 Table 4.
No LLM involved — pure rule lookup, always reproducible.
"""

# ISO 26262-3 Table 4: ASIL[Severity][Exposure][Controllability]
# Axes: S0-S3, E0-E4, C0-C3
ASIL_TABLE = {
    "S0": {
        "E0": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E1": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E2": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E3": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E4": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
    },
    "S1": {
        "E0": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E1": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E2": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E3": {"C0": "QM", "C1": "QM", "C2": "A",  "C3": "B"},
        "E4": {"C0": "QM", "C1": "QM", "C2": "A",  "C3": "B"},
    },
    "S2": {
        "E0": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E1": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E2": {"C0": "QM", "C1": "QM", "C2": "A",  "C3": "B"},
        "E3": {"C0": "QM", "C1": "A",  "C2": "B",  "C3": "C"},
        "E4": {"C0": "QM", "C1": "A",  "C2": "B",  "C3": "C"},
    },
    "S3": {
        "E0": {"C0": "QM", "C1": "QM", "C2": "QM", "C3": "QM"},
        "E1": {"C0": "QM", "C1": "QM", "C2": "A",  "C3": "B"},
        "E2": {"C0": "QM", "C1": "A",  "C2": "B",  "C3": "C"},
        "E3": {"C0": "A",  "C1": "B",  "C2": "C",  "C3": "D"},
        "E4": {"C0": "A",  "C1": "B",  "C2": "C",  "C3": "D"},
    },
}

SEVERITY_DESC = {
    "S0": "No injuries",
    "S1": "Light to moderate injuries",
    "S2": "Severe to life-threatening injuries (survival probable)",
    "S3": "Life-threatening injuries (survival uncertain) or fatal",
}

EXPOSURE_DESC = {
    "E0": "Incredible — almost never occurs",
    "E1": "Very low probability",
    "E2": "Low probability",
    "E3": "Medium probability",
    "E4": "High probability — occurs frequently",
}

CONTROLLABILITY_DESC = {
    "C0": "Controllable in general",
    "C1": "Simply controllable",
    "C2": "Normally controllable",
    "C3": "Difficult to control or uncontrollable",
}

ASIL_FULL = {
    "QM": "QM (Quality Management)",
    "A": "ASIL A",
    "B": "ASIL B",
    "C": "ASIL C",
    "D": "ASIL D",
}


def compute_asil(S: str, E: str, C: str) -> str:
    """
    Compute ASIL level from Severity, Exposure, Controllability.
    
    Args:
        S: Severity class — "S0", "S1", "S2", or "S3"
        E: Exposure class — "E0", "E1", "E2", "E3", or "E4"
        C: Controllability class — "C0", "C1", "C2", or "C3"
    
    Returns:
        ASIL level string: "QM", "A", "B", "C", or "D"
    
    Raises:
        ValueError: if any parameter is out of range
    """
    S, E, C = S.upper(), E.upper(), C.upper()

    if S not in ASIL_TABLE:
        raise ValueError(f"Invalid Severity '{S}'. Must be S0–S3.")
    if E not in ASIL_TABLE[S]:
        raise ValueError(f"Invalid Exposure '{E}'. Must be E0–E4.")
    if C not in ASIL_TABLE[S][E]:
        raise ValueError(f"Invalid Controllability '{C}'. Must be C0–C3.")

    return ASIL_TABLE[S][E][C]


def asil_rationale(S: str, E: str, C: str) -> str:
    """
    Return a human-readable rationale string for the ASIL determination.
    """
    S, E, C = S.upper(), E.upper(), C.upper()
    level = compute_asil(S, E, C)
    full_level = ASIL_FULL.get(level, level)

    return (
        f"**{full_level}** — determined per ISO 26262-3 Table 4:\n"
        f"- **Severity {S}**: {SEVERITY_DESC.get(S, S)}\n"
        f"- **Exposure {E}**: {EXPOSURE_DESC.get(E, E)}\n"
        f"- **Controllability {C}**: {CONTROLLABILITY_DESC.get(C, C)}"
    )


def get_asil_color(asil: str) -> str:
    """Return a Streamlit-compatible color for the ASIL badge."""
    colors = {
        "QM": "gray",
        "A":  "yellow",
        "B":  "orange",
        "C":  "red",
        "D":  "red",
    }
    return colors.get(asil.upper(), "gray")