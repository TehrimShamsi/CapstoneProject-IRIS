import os
from pathlib import Path
from fastapi import UploadFile

class PDFProcessor:
    def __init__(self):
        self.base = Path("data/pdfs")
        self.base.mkdir(parents=True, exist_ok=True)

    def save_pdf(self, file: UploadFile, paper_id: str) -> str:
        path = self.base / f"{paper_id}.pdf"
        with open(path, "wb") as f:
            f.write(file.file.read())
        return str(path)

    def extract_text(self, pdf_path: str) -> str:
        # placeholder simple extractor (works for most text PDFs)
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
