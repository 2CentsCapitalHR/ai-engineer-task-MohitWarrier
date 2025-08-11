import os
from docx import Document

OUT_DIR = "data/uploads/flawed"

SAMPLES_FLAWED = {
    # 1) AoA: Wrong jurisdiction + missing Signatories
    "AoA_WRONG_JURISDICTION.docx": """Articles of Association

Company Name: Example Technologies FZ-LLC
Jurisdiction: UAE Federal Court
Registered Address: 1234, Al Maryah Island, Abu Dhabi

Directors:
- Adam Smith
- Priya Patel

Shareholders:
- Adam Smith (51%)
- Priya Patel (49%)

Purpose:
Technology solutions and software development

Governing Law:
This document is governed by the laws of the United Arab Emirates.

Date: 9 August 2025
""",

    # 2) MoA: Missing Registered Address clause
    "MoA_MISSING_ADDRESS.docx": """Memorandum of Association

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market

Objectives:
- Provide software development and consulting
- Operate within ADGM regulatory framework

Shareholders:
- Adam Smith (51%)
- Priya Patel (49%)

Capital Structure:
- Authorized Shares: 1000
- Issued Shares: 1000

Signatories:
- Adam Smith (Shareholder)
- Priya Patel (Shareholder)

Date: 9 August 2025
""",

    # 3) Board Resolution: Missing Signatories + ambiguous language
    "Board_Resolution_AMBIGUOUS_NO_SIG.docx": """Board Resolution

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market
Resolution Number: BR-2025-002
Date: 9 August 2025

Resolved:
- The Board may consider approving incorporation documents where possible.
- The Company may consider authorizing a representative to sign documents.

""",

    # 4) Register: Fine for signatures (we won't require), but include "UAE Federal Court" to trigger RF
    "Register_WITH_BAD_REFERENCE.docx": """Register of Members and Directors

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market

Directors:
- Adam Smith
- Priya Patel

Shareholders (Members):
- Adam Smith — 510 Shares
- Priya Patel — 490 Shares

Note:
Any disputes shall be settled in the UAE Federal Court.

Effective Date: 9 August 2025
""",

    # 5) UBO: Missing "Ultimate Beneficial Owner" phrase and missing Signatories
    "UBO_MISSING_UBO_AND_SIG.docx": """Ultimate Beneficial Owner (UBO) Declaration Form

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market

Ownership:
- Adam Smith — 51%
- Priya Patel — 49%

Declaration:
The undersigned declare that the information provided herein regarding ownership is true and accurate.

Date: 9 August 2025
"""
}

def write_docx(path, text):
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(path)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for fname, content in SAMPLES_FLAWED.items():
        path = os.path.join(OUT_DIR, fname)
        write_docx(path, content)
        print(f"Wrote {path}")

if __name__ == "__main__":
    main()
