from pypdf import PdfReader
import os

def get_knowledge_base(pdf_path, txt_path):
    # 1. Read the PDF
    reader = PdfReader(pdf_path)
    cv_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            cv_text += text + "\n"
    
    # 2. Read the Summary
    with open(txt_path, "r", encoding="utf-8") as f:
        summary_text = f.read()
        
    return f"## Summary:\n{summary_text}\n\n## LinkedIn Profile:\n{cv_text}"