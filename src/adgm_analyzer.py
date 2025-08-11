import json
from typing import Dict, List, Any, Optional


def load_rules(json_path: str = "config/adgm_rules.json") -> Dict[str, Any]:
    """
    Loads the ADGM compliance rules from JSON.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_required_clauses(doc_info: Dict[str, Any], doc_type: str, rules: Dict[str, Any]) -> List[str]:
    """
    Check presence of required clauses in the document's full text.
    Returns a list of missing clause keywords.
    """
    text = (doc_info.get("full_text") or "").lower()
    # Defensive: ensure structure exists
    clauses_per_doc = rules.get("clauses_per_doc", {})
    required_clauses = clauses_per_doc.get(doc_type, []) or []

    missing: List[str] = []
    for clause in required_clauses:
        key = str(clause).strip()
        if not key:
            continue
        if key.lower() not in text:
            missing.append(key)
    return missing


def find_red_flags(doc_info: Dict[str, Any], doc_type: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Simple rule-based red flag detector, scoped by document type.
    Returns a list of dicts: {issue, severity, match}
    """
    text = (doc_info.get("full_text") or "").lower()
    flags: List[Dict[str, str]] = []

    # Incorrect jurisdiction
    if "uae federal court" in text:
        flags.append({
            "issue": "References UAE Federal Court instead of ADGM",
            "severity": "High",
            "match": "UAE Federal Court"
        })

    # Ambiguous language (a few common variants)
    ambiguous_markers = [
        "may consider",
        "where possible",
        "as appropriate",
        "at its discretion"
    ]
    if any(m in text for m in ambiguous_markers):
        flags.append({
            "issue": "Ambiguous or non-binding language",
            "severity": "Medium",
            "match": "; ".join(ambiguous_markers)
        })

    # Signature requirements: only for docs that conventionally require signatures
    requires_signature = {
        "Articles of Association",
        "Memorandum of Association",
        "Board Resolution",
        "Shareholder Resolution",
        "UBO Declaration Form",
        "Incorporation Application Form"
    }
    if (doc_type in requires_signature) and ("sign" not in text and "signature" not in text):
        flags.append({
            "issue": "Appears to be missing signatory section",
            "severity": "High",
            "match": "signature"
        })

    return flags


def build_issue_report(
    file_name: str,
    doc_type: str,
    missing_clauses: List[str],
    red_flags: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """
    Returns a list of issue dicts for JSON summary.
    """
    issues: List[Dict[str, str]] = []

    for clause in missing_clauses:
        issues.append({
            "document": doc_type,
            "section": "N/A",
            "issue": f"Missing required clause: {clause}",
            "severity": "High",
            "suggestion": f"Add clause referencing '{clause}'."
        })

    for rf in red_flags:
        issues.append({
            "document": doc_type,
            "section": "N/A",
            "issue": rf.get("issue", "Flagged issue"),
            "severity": rf.get("severity", "Medium"),
            "suggestion": "Align with ADGM wording where applicable."
        })

    return issues


def infer_doc_type_from_text(text: Optional[str]) -> str:
    """
    Fallback document type classifier from content.
    """
    t = (text or "").lower()
    if "articles of association" in t:
        return "Articles of Association"
    if "memorandum of association" in t or "memorandum of understanding" in t or "moa" in t or "mou" in t:
        return "Memorandum of Association"
    if "register of members" in t or "register of directors" in t:
        return "Register of Members and Directors"
    if "board resolution" in t:
        return "Board Resolution"
    if "ultimate beneficial owner" in t or "ubo" in t:
        return "UBO Declaration Form"
    return "Unknown"
