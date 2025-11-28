import os
from pathlib import Path
from fastapi import UploadFile

# Import shared config
try:
    from app.config import PDFS_DIR
except ImportError:
    PDFS_DIR = Path("data/pdfs")
    PDFS_DIR.mkdir(parents=True, exist_ok=True)

class PDFProcessor:
    """
    Handles PDF storage and text extraction.
    Uses centralized storage directory (data/pdfs/).
    """
    
    def __init__(self):
        self.base = PDFS_DIR
        self.base.mkdir(parents=True, exist_ok=True)

    def save_pdf(self, file: UploadFile, paper_id: str) -> str:
        """
        Save uploaded PDF file to storage.
        
        Args:
            file: FastAPI UploadFile object
            paper_id: Unique identifier for the paper
            
        Returns:
            Full path to saved PDF
        """
        path = self.base / f"{paper_id}.pdf"
        with open(path, "wb") as f:
            f.write(file.file.read())
        return str(path)

    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from PDF using PyPDF2.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        # Check if file exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found at {pdf_path}")
        
        import PyPDF2
        try:
            reader = PyPDF2.PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from {pdf_path}: {e}")