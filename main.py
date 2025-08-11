import gradio as gr
from src.document_processor import (
    extract_text_and_sections,
    find_paragraph_indexes,
    annotate_paragraph,
    save_reviewed_copy,
)
from src.adgm_analyzer import (
    load_rules,
    check_required_clauses,
    find_red_flags,
    build_issue_report,
    infer_doc_type_from_text,
)
from src.ai_agent import (
    generate_ai_suggestions_for_file,
    normalize_issue_key,           
    doc_type_accepts_issue_key,    
)
from docx import Document
import os, json, time, zipfile

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def infer_doc_type_from_filename(file_path):
    fname = os.path.basename(file_path).lower()
    if "articles" in fname:
        return "Articles of Association"
    if "memorandum" in fname or "mou" in fname:
        return "Memorandum of Association"
    if "register" in fname:
        return "Register of Members and Directors"
    if "resolution" in fname:
        return "Board Resolution"
    if "ubo" in fname:
        return "UBO Declaration Form"
    return "Unknown"


def detect_process_from_doc_types(doc_types):
    dt = {str(d).lower() for d in doc_types}
    incorporation_markers = {
        "articles of association",
        "memorandum of association",
        "board resolution",
        "shareholder resolution",
        "ubo declaration form",
        "register of members and directors",
        "incorporation application form",
        "change of registered address notice",
    }
    if dt & {m.lower() for m in incorporation_markers}:
        return "Company Incorporation"
    return "Unknown"


def write_json_report(summary_dict, out_dir="data/output"):
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(out_dir, f"analysis_summary_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_dict, f, indent=2, ensure_ascii=False)
    return json_path


def zip_outputs(file_paths, zip_out_path=None):
    os.makedirs("data/output", exist_ok=True)
    if zip_out_path is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        zip_out_path = os.path.join("data/output", f"reviewed_package_{ts}.zip")
    with zipfile.ZipFile(zip_out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in file_paths:
            if os.path.isfile(p):
                zf.write(p, arcname=os.path.basename(p))
    return zip_out_path


def analyze_files(use_ai, file_paths):
    if not file_paths:
        return "No files received. Please upload one or more .docx files.", None

    rules = load_rules()
    found_docs, detected_doc_types = [], []
    results, all_issues, reviewed_paths = [], [], []

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ai_active = bool(use_ai and OPENAI_API_KEY)
    print("[DEBUG] Use AI toggle:", use_ai)
    print("[DEBUG] OPENAI_API_KEY present:", bool(OPENAI_API_KEY))
    print("[DEBUG] AI active (toggle AND key):", ai_active)
    if OPENAI_API_KEY:
        print("[DEBUG] OPENAI head/tail:", OPENAI_API_KEY[:4], OPENAI_API_KEY[-4:])

    for file_path in file_paths:
        print("\n[DEBUG] Processing file:", file_path)

        # 1) Infer type
        doc_type = infer_doc_type_from_filename(file_path)
        print("[DEBUG] Doc type from filename:", doc_type)

        # 2) Extract
        with open(file_path, "rb") as f:
            doc_info = extract_text_and_sections(f)
        paragraphs = doc_info["paragraphs"]
        print("[DEBUG] Extracted paragraphs:", len(paragraphs))

        # 3) Fallback type
        if doc_type == "Unknown":
            doc_type = infer_doc_type_from_text(doc_info.get("full_text", "")) or "Unknown"
            print("[DEBUG] Doc type from content:", doc_type)

        found_docs.append(doc_type.lower())
        detected_doc_types.append(doc_type)

        # 4) Rules
        missing_clauses = check_required_clauses(doc_info, doc_type, rules)
        try:
            red_flags = find_red_flags(doc_info, doc_type)
        except TypeError:
            red_flags = find_red_flags(doc_info)
        print("[DEBUG] Missing clauses:", missing_clauses)
        print("[DEBUG] Red flags:", red_flags)

        # 5) Issues
        file_issues = build_issue_report(os.path.basename(file_path), doc_type, missing_clauses, red_flags)
        print("[DEBUG] Rule-based issues for JSON:", file_issues)

        # 6) AI suggestions 
        ai_suggestions = []
        if ai_active:
            try:
                refs_exists = os.path.isfile("data/adgm_refs.txt")
                print("[DEBUG] refs file exists:", refs_exists)
                ai_suggestions = generate_ai_suggestions_for_file(
                    doc_text=doc_info.get("full_text", ""),
                    issues_for_file=file_issues,
                    refs_path="data/adgm_refs.txt",
                    api_key=OPENAI_API_KEY,
                    model="llama-3.1-8b-instant",
                )
                print("[DEBUG] AI suggestions count:", len(ai_suggestions))
                if ai_suggestions[:2]:
                    print("[DEBUG] AI suggestion sample:", ai_suggestions[:2])
            except Exception as e:
                print("[ERROR] AI suggestion error:", repr(e))
                ai_suggestions = []

            # Merge into issues with improved matching and cross-file filtering
            if ai_suggestions:
                # Precompute normalized keys for current file issues
                issue_keys_current = [normalize_issue_key(i.get("issue", "")) for i in file_issues]

                for sug in ai_suggestions:
                    sug_issue_raw = (sug.get("issue") or "").strip()
                    sug_key = normalize_issue_key(sug_issue_raw)

                    # Only accept suggestions whose normalized key is allowed for this doc_type
                    if not doc_type_accepts_issue_key(doc_type, sug_key):
                        print(f"[DEBUG] Skip AI suggestion not applicable to {doc_type}: {sug_issue_raw}")
                        continue

                    matched = False
                    for idx, issue in enumerate(file_issues):
                        issue_title = issue.get("issue", "")
                        issue_key = issue_keys_current[idx]
                        if sug_key and issue_key and (sug_key in issue_key or issue_key in sug_key):
                            issue["suggestion_ai"] = sug.get("suggestion", "")
                            issue["rationale_ai"] = sug.get("rationale", "")
                            issue["citation_label"] = sug.get("citation_label", "")
                            matched = True
                            break

                    if not matched:
                        # If not matched to a specific issue but applicable to doc_type, add as separate entry
                        file_issues.append({
                            "document": doc_type,
                            "section": "N/A",
                            "issue": sug_issue_raw or "AI-suggested improvement",
                            "severity": "Medium",
                            "suggestion": "",
                            "suggestion_ai": sug.get("suggestion", ""),
                            "rationale_ai": sug.get("rationale", ""),
                            "citation_label": sug.get("citation_label", "")
                        })

        all_issues.extend(file_issues)

        # 7) Annotate
        doc = Document(file_path)

        # Dedup guard for AI and rule-based comments on same paragraph
        seen_comments = set()  # tuples of (paragraph_index, normalized_comment_text)

        for clause in missing_clauses:
            hit_idxs = find_paragraph_indexes(clause, paragraphs)
            target_idx = hit_idxs[0] if hit_idxs else max(0, len(paragraphs) - 1)
            comment_text = f"Missing required clause: {clause}"
            key = (target_idx, comment_text.lower().strip())
            if key not in seen_comments:
                annotate_paragraph(doc, target_idx, comment_text, highlight="YELLOW")
                seen_comments.add(key)

        for rf in red_flags:
            match = rf.get("match", "")
            hit_idxs = find_paragraph_indexes(match, paragraphs) if match else []
            target_idx = hit_idxs[0] if hit_idxs else max(0, len(paragraphs) - 1)
            comment_text = f"Red flag: {rf['issue']}"
            key = (target_idx, comment_text.lower().strip())
            if key not in seen_comments:
                annotate_paragraph(doc, target_idx, comment_text, highlight="RED")
                seen_comments.add(key)

        if ai_suggestions:
            for sug in ai_suggestions:
                # Target by normalized key to reduce duplicates
                raw_issue = (sug.get("issue") or "")
                key_phrase = raw_issue.split(":")[0].strip()
                idxs = find_paragraph_indexes(key_phrase, paragraphs) if key_phrase else []
                tgt = idxs[0] if idxs else max(0, len(paragraphs) - 1)
                tag = sug.get("citation_label", "ADGM Reference")
                comment = f"AI Suggestion: {sug.get('suggestion','')}"
                if tag:
                    comment += f" | Source: {tag}"
                dedup_key = (tgt, comment.lower().strip())
                if dedup_key in seen_comments:
                    continue
                annotate_paragraph(doc, tgt, comment, highlight="YELLOW")
                seen_comments.add(dedup_key)

        reviewed_path = save_reviewed_copy(file_path, doc, output_dir="data/output")
        reviewed_paths.append(reviewed_path)
        print("[DEBUG] Saved reviewed file:", reviewed_path)

        line = f"{os.path.basename(file_path)} ({doc_type}): "
        line += ("No required clauses missing." if not missing_clauses else f"Missing clauses: {', '.join(missing_clauses)}")
        if red_flags:
            line += f"\n  Red Flags: {', '.join([rf['issue'] for rf in red_flags])}"
        if ai_suggestions:
            line += f"\n  AI Suggestions: {len(ai_suggestions)} added"
        results.append(line)

    missing_docs = [doc for doc in rules.get("required_documents", []) if doc.lower() not in found_docs]
    print("[DEBUG] Missing documents at set level:", missing_docs)

    detected_process = detect_process_from_doc_types(detected_doc_types)
    print("[DEBUG] Detected process:", detected_process)

    summary = {
        "process": detected_process,
        "documents_uploaded": len(file_paths),
        "required_documents": len(rules.get("required_documents", [])),
        "missing_documents": missing_docs,
        "issues_found": all_issues,
        "reviewed_files": reviewed_paths,
        "ai_used": ai_active,
    }

    text_summary = "\n\n".join(results)
    if missing_docs:
        text_summary += f"\n\nMissing required documents: {', '.join(missing_docs)}"
    text_summary += "\n\nReviewed copies saved in data/output/"

    json_report_path = write_json_report(summary, out_dir="data/output")
    package_path = zip_outputs(reviewed_paths + [json_report_path])

    text_summary += f"\n\nPackaged download created: {os.path.basename(package_path)}"
    text_summary += "\n\nJSON Summary:\n" + json.dumps(summary, indent=2)

    print("[DEBUG] AI used flag (summary):", summary["ai_used"])
    return text_summary, package_path


iface = gr.Interface(
    fn=analyze_files,
    inputs=[
        gr.Checkbox(label="Use AI (RAG)", value=False),
        gr.Files(type="filepath", label="Upload .docx files"),
    ],
    outputs=[gr.Textbox(label="Summary"), gr.File(label="Download Reviewed Package (.zip)")],
    title="ADGM Document Analyzer Demo",
    description="Upload your .docx files. The app checks completeness/clauses, flags red flags, annotates docs, and provides a JSON + ZIP download. Optionally, enable AI (RAG) for grounded suggestions.",
    flagging_mode="never",
)

if __name__ == "__main__":
    iface.launch()
