"""
LangChain chains for HARA workflow steps using GROQ LLM.
All prompts are module-level constants for easy review and audit.
"""

import os
import json
import re
from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Controlled Prompts ────────────────────────────────────────────────────────

HAZARD_SYSTEM_PROMPT = """You are a certified Functional Safety Engineer specializing in ISO 26262 HARA 
(Hazard Analysis and Risk Assessment) for automotive systems.

Your task is to identify hazards and hazardous events from the provided system architecture context.

STRICT RULES:
- Only identify hazards that are directly supported by evidence in the provided context
- Each hazardous event must reference a specific page or section from the context
- Follow ISO 26262 terminology: Hazard → Hazardous Event → Operational Situation
- Output ONLY valid JSON — no markdown, no explanation outside the JSON

OUTPUT FORMAT (JSON array):
[
  {
    "id": "HE-001",
    "hazard": "<physical or functional failure mode>",
    "hazardous_event": "<hazard + operational situation combined>",
    "operational_situation": "<driving scenario where hazard occurs>",
    "affected_function": "<system function affected>",
    "source_evidence": "<quote or reference from the context, including page number>"
  }
]"""

SEC_SYSTEM_PROMPT = """You are a certified Functional Safety Engineer performing HARA classification 
per ISO 26262-3.

Given a hazardous event and system context, suggest Severity (S), Exposure (E), and Controllability (C) 
ratings with clear rationale.

CLASSIFICATION SCALES (ISO 26262-3):
Severity:       S0=No injury, S1=Light-moderate, S2=Severe-life threatening, S3=Fatal/life uncertain
Exposure:       E0=Incredible, E1=Very low, E2=Low, E3=Medium, E4=High
Controllability:C0=Generally, C1=Simply, C2=Normally, C3=Difficult/uncontrollable

STRICT RULES:
- Base ratings on the operational situation described
- Provide a single concise sentence of rationale for each rating
- Consider worst-case realistic scenario, not best-case
- Output ONLY valid JSON — no markdown, no preamble

OUTPUT FORMAT (JSON object):
{
  "S": "S3",
  "S_rationale": "<one sentence justification>",
  "E": "E3",
  "E_rationale": "<one sentence justification>",
  "C": "C2",
  "C_rationale": "<one sentence justification>"
}"""

GOAL_SYSTEM_PROMPT = """You are a certified Functional Safety Engineer drafting Safety Goals and 
Safety Requirements per ISO 26262.

Given a hazardous event and its ASIL level, draft:
1. Safety Goal (SG) — high-level safety objective, technology-independent
2. Functional Safety Requirement (FSR) — functional behavior required to meet the SG
3. Technical Safety Requirement (TSR) — technical/implementation-level requirement

QUALITY RULES for requirements:
- Must contain a measurable condition or quantifiable target
- Must use active voice with a clear verb (shall, must)
- Must be unambiguous and testable
- FSR must be technology-independent
- TSR must reference a specific technical mechanism or threshold
- Flag any requirement that violates these rules in quality_flags

Output ONLY valid JSON — no markdown, no preamble.

OUTPUT FORMAT (JSON object):
{
  "safety_goal": "<SG statement>",
  "fsr": "<FSR statement>",
  "tsr": "<TSR statement>",
  "quality_flags": ["<flag if any requirement is vague or untestable>"]
}"""


def get_llm() -> ChatGroq:
    """Initialize GROQ LLM with controlled temperature."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.2,
        max_tokens=4096,
    )


def _parse_json_response(response_text: str) -> Any:
    """
    Safely parse JSON from LLM response.
    Handles cases where LLM wraps JSON in markdown code blocks.
    """
    text = response_text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()
    return json.loads(text)


def suggest_hazards(context: str, system_description: str) -> List[Dict[str, Any]]:
    """
    Use LLM to suggest hazards and hazardous events from retrieved context.
    
    Args:
        context: Formatted retrieved chunks from FAISS
        system_description: Brief description of the system under analysis
    
    Returns:
        List of hazard event dicts with id, hazard, hazardous_event, etc.
    """
    llm = get_llm()
    user_msg = f"""System Under Analysis: {system_description}

Retrieved System Context:
{context}

Identify all hazards and hazardous events present in this system context. 
Return a JSON array following the specified format."""

    messages = [
        SystemMessage(content=HAZARD_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = llm.invoke(messages)
    result = _parse_json_response(response.content)

    if isinstance(result, list):
        return result
    return []


def suggest_sec(context: str, hazardous_event: str, operational_situation: str) -> Dict[str, Any]:
    """
    Suggest S, E, C ratings with rationale for a given hazardous event.
    
    Args:
        context: Formatted retrieved chunks from FAISS
        hazardous_event: The hazardous event description
        operational_situation: The operational scenario
    
    Returns:
        Dict with S, E, C values and rationale strings
    """
    llm = get_llm()
    user_msg = f"""Hazardous Event: {hazardous_event}
Operational Situation: {operational_situation}

System Context:
{context}

Classify the Severity (S), Exposure (E), and Controllability (C) for this hazardous event.
Return a JSON object following the specified format."""

    messages = [
        SystemMessage(content=SEC_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = llm.invoke(messages)
    return _parse_json_response(response.content)


def draft_safety_goals(
    context: str,
    hazardous_event: str,
    asil: str,
    affected_function: str,
) -> Dict[str, Any]:
    """
    Draft Safety Goal, FSR, and TSR for an approved hazardous event.
    
    Args:
        context: Formatted retrieved chunks from FAISS
        hazardous_event: The approved hazardous event description
        asil: Determined ASIL level (e.g., "ASIL D")
        affected_function: The system function affected by this hazard
    
    Returns:
        Dict with safety_goal, fsr, tsr, quality_flags
    """
    llm = get_llm()
    user_msg = f"""Hazardous Event: {hazardous_event}
Affected Function: {affected_function}
ASIL Level: {asil}

System Context:
{context}

Draft a Safety Goal (SG), Functional Safety Requirement (FSR), and 
Technical Safety Requirement (TSR) for this hazardous event at {asil}.
Return a JSON object following the specified format."""

    messages = [
        SystemMessage(content=GOAL_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = llm.invoke(messages)
    result = _parse_json_response(response.content)

    # Ensure quality_flags is always a list
    if "quality_flags" not in result:
        result["quality_flags"] = []

    return result