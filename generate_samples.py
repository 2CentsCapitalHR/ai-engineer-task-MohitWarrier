import os
from docx import Document

OUT_DIR = "data/uploads"

SAMPLES = {
    "Articles_of_Association.docx": """Articles of Association

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market
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
This document is governed by the laws of the Abu Dhabi Global Market.

Signatories:
- Adam Smith (Director)
- Priya Patel (Director)

Date: 9 August 2025
""",
    "Memorandum_of_Association.docx": """Memorandum of Association

Company Name: Example Technologies FZ-LLC
Registered Address: 1234, Al Maryah Island, Abu Dhabi
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
    "Register_of_Members_and_Directors.docx": """Register of Members and Directors

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market

Directors:
- Adam Smith
- Priya Patel

Shareholders (Members):
- Adam Smith — 510 Shares
- Priya Patel — 490 Shares

Effective Date: 9 August 2025
""",
    "Board_Resolution.docx": """Board Resolution

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market
Resolution Number: BR-2025-001
Date: 9 August 2025

Resolved:
- Approve incorporation documents for Example Technologies FZ-LLC
- Authorize Adam Smith to sign all necessary documents on behalf of the Company

Signatories:
- Adam Smith (Director)
- Priya Patel (Director)
""",
    "UBO_Declaration_Form.docx": """Ultimate Beneficial Owner (UBO) Declaration Form

Company Name: Example Technologies FZ-LLC
Jurisdiction: Abu Dhabi Global Market

Ultimate Beneficial Owner(s):
- Adam Smith — 51%
- Priya Patel — 49%

Declaration:
The undersigned declare that the information provided herein regarding the ultimate beneficial ownership of the Company is true and accurate to the best of our knowledge.

Signatories:
- Adam Smith
- Priya Patel

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
    for fname, content in SAMPLES.items():
        path = os.path.join(OUT_DIR, fname)
        write_docx(path, content)
        print(f"Wrote {path}")

if __name__ == "__main__":
    main()
