import subprocess, json
from ..storage.pdf_store import save_pdf_to_storage
from ..utils.logging import logger

class ParserAgent:
    def __init__(self):
        pass

    def parse_pdf(self, pdf_path, paper_id):
        # 1) use PyMuPDF or pdfplumber to extract text and page offsets
        # 2) call GROBID (if running) to parse references/metadata (optional)
        # simplified stub:
        text = self.extract_text_local(pdf_path)
        structured = self.structure_text_into_sections(text)
        # call grobid for references (if available)
        try:
            grobid_output = self.call_grobid(pdf_path)
            structured["references"] = grobid_output
        except Exception:
            structured["references"] = []
        structured["paper_id"] = paper_id
        return structured

    def extract_text_local(self, pdf_path):
        # use PyMuPDF to get full text
        import fitz
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        return "\n".join(pages)

    def call_grobid(self, pdf_path):
        # example: curl -F "input=@file.pdf" http://localhost:8070/api/processReferences
        raise NotImplementedError
