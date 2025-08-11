import os
from typing import List, Dict, Any
import re
import requests
import json


def load_refs(refs_path: str = "data/adgm_refs.txt") -> List[Dict[str, str]]:
    if not os.path.isfile(refs_path):
        return []
    refs: List[Dict[str, str]] = []
    label = None
    buf: List[str] = []
    with open(refs_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.rstrip("\n")
            if not s.strip():
                if label and buf:
                    refs.append({"label": label, "text": " ".join(buf).strip()})
                label, buf = None, []
                continue
            m = re.match(r"^\[(.+?)\]\s*$", s)
            if m:
                if label and buf:
                    refs.append({"label": label, "text": " ".join(buf).strip()})
                label = m.group(1).strip()
                buf = []
            else:
                buf.append(s.strip())
        if label and buf:
            refs.append({"label": label, "text": " ".join(buf).strip()})
    return refs


def _score_overlap(query: str, text: str) -> int:
    q = set(re.findall(r"[a-z]+", (query or "").lower()))
    t = set(re.findall(r"[a-z]+", (text or "").lower()))
    if not q or not t:
        return 0
    return len(q & t)


def retrieve_top_k(query: str, refs: List[Dict[str, str]], k: int = 3) -> List[Dict[str, str]]:
    scored = [(r, _score_overlap(query, r.get("text", ""))) for r in refs]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [r for (r, s) in scored[:k] if s > 0]
    return top


def build_issue_prompt(doc_text: str, issues: List[Dict[str, Any]], retrieved: List[Dict[str, str]]) -> str:
    refs_block = "\n".join([f"- {r['label']}: {r['text']}" for r in retrieved]) or "None"
    issues_block = "\n".join([
        f"- Document: {it.get('document','Unknown')}; Issue: {it.get('issue','')} (Severity: {it.get('severity','')})"
        for it in issues
    ]) or "None"
    prompt = (
        "You are a legal assistant focused on ADGM compliance. Based on the user's document text and "
        "the retrieved ADGM reference snippets, do the following for each issue:\n"
        "1) Provide a brief rationale explaining the problem in context of ADGM.\n"
        "2) Suggest a short, compliant clause or wording to fix the problem (concise).\n"
        "3) Cite one of the retrieved snippet labels as a pointer (not a URL).\n\n"
        f"Retrieved ADGM references:\n{refs_block}\n\n"
        f"Issues:\n{issues_block}\n\n"
        "Document text (truncated if long):\n"
        f"{doc_text[:4000]}\n\n"
        "Return a JSON list; each item with keys: issue, rationale, suggestion, citation_label."
    )
    return prompt


def call_groq_compatible_chat(prompt: str, api_key: str, model: str = "llama-3.1-8b-instant") -> str:
    """
    Calls Groq's OpenAI-compatible Chat Completions with the key from OPENAI_API_KEY.
    Endpoint: https://api.groq.com/openai/v1/chat/completions
    """
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set.")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 600,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    try:
        resp.raise_for_status()
    except Exception:
        print("[ERROR][AI] Groq-compatible response:", resp.status_code, resp.text)
        raise
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def parse_ai_response_to_list(text: str) -> List[Dict[str, str]]:
    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
        return json.loads(text)
    except Exception:
        return []


def normalize_issue_key(text: str) -> str:
    """
    Normalize an issue string to a simple key:
    - lowercased
    - remove common prefixes like 'missing required clause:' and 'red flag:'
    - keep core nouns like 'signatories', 'jurisdiction', 'registered address', 'ambiguity'
    - collapse whitespace
    """
    t = (text or "").lower().strip()
    # remove common prefixes
    t = re.sub(r"^(missing required clause|red flag)\s*:\s*", "", t)
    # map common long phrases to compact keys
    replacements = [
        (r"abu dhabi global market", "adgm"),
        (r"u\.?a\.?e\.?\s*federal court", "uae federal court"),
        (r"registered address", "registered address"),
        (r"signatories?", "signatories"),
        (r"jurisdiction", "jurisdiction"),
        (r"ambiguous.*language|non-binding", "ambiguity"),
        (r"appears to be missing signatory section", "signatories"),
    ]
    for pat, rep in replacements:
        t = re.sub(pat, rep, t)
    # keep only letters, digits, spaces
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def doc_type_accepts_issue_key(doc_type: str, issue_key: str) -> bool:
    dt = (doc_type or "").lower()
    k = (issue_key or "").lower()
    if not k:
        return False

    # Broad buckets
    COMMON = {"jurisdiction", "adgm", "ambiguity", "signatories"}

    # Doc-specific keys
    AOA_KEYS = COMMON | {"company name", "objects", "share capital", "directors", "dividends"}
    MOA_KEYS = COMMON | {"registered address", "objects", "share capital"}
    RES_KEYS = COMMON | {"resolution approval", "authorized representative"}
    REG_KEYS = COMMON | {"register", "members", "directors"}
    UBO_KEYS = COMMON | {"ubo", "beneficial owner", "declaration"}

    if "articles of association" in dt:
        allow = AOA_KEYS
    elif "memorandum of association" in dt:
        allow = MOA_KEYS
    elif "board resolution" in dt:
        allow = RES_KEYS
    elif "register of members and directors" in dt:
        allow = REG_KEYS
    elif "ubo" in dt:
        allow = UBO_KEYS
    else:
        allow = COMMON

    # accept if any allow token is contained in the issue key
    return any(tok in k for tok in allow)


def generate_ai_suggestions_for_file(
    doc_text: str,
    issues_for_file: List[Dict[str, Any]],
    refs_path: str = "data/adgm_refs.txt",
    api_key: str = "",
    model: str = "llama-3.1-8b-instant",
) -> List[Dict[str, str]]:
    refs = load_refs(refs_path)
    print("[DEBUG][AI] Loaded refs:", len(refs))
    issue_query = " ".join([i.get("issue", "") for i in issues_for_file])[:500]
    top_refs = retrieve_top_k(issue_query or doc_text[:500], refs, k=3)
    print("[DEBUG][AI] Retrieved top refs:", [r.get("label") for r in top_refs])

    prompt = build_issue_prompt(doc_text, issues_for_file, top_refs)
    raw = call_groq_compatible_chat(prompt, api_key=api_key, model=model)
    print("[DEBUG][AI] Raw model output length:", len(raw) if isinstance(raw, str) else type(raw))

    suggestions = parse_ai_response_to_list(raw)
    print("[DEBUG][AI] Parsed suggestions count:", len(suggestions))

    if suggestions and top_refs:
        if any("citation_label" not in s for s in suggestions):
            default_label = top_refs[0]["label"]
            for s in suggestions:
                s.setdefault("citation_label", default_label)
    return suggestions
