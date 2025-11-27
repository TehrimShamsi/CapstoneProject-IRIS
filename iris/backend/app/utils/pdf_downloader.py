# backend/app/utils/pdf_downloader.py
"""
Utility for downloading PDFs from ArXiv with SSL handling
"""
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Optional

try:
    from app.utils.observability import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class PDFDownloader:
    """Download PDFs from ArXiv with proper SSL handling"""
    
    def __init__(self, download_dir: str = "papers"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Create SSL context that doesn't verify certificates
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def download_arxiv_pdf(self, arxiv_id: str, output_path: Optional[str] = None) -> str:
        """
        Download a PDF from ArXiv.
        
        Args:
            arxiv_id: ArXiv paper ID (with or without version suffix)
            output_path: Optional custom output path
            
        Returns:
            Path to downloaded PDF
        """
        # Clean the arxiv_id (remove version suffix for URL)
        clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id and arxiv_id.split('v')[-1].isdigit() else arxiv_id
        
        # Construct ArXiv PDF URL
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
        
        # Determine output path
        if output_path is None:
            safe_id = arxiv_id.replace('/', '_').replace(':', '_')
            output_path = str(self.download_dir / f"{safe_id}.pdf")
        
        logger.info(f"Downloading PDF from {pdf_url}")
        
        try:
            # Create request with SSL context
            request = urllib.request.Request(
                pdf_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            # Download with unverified SSL
            with urllib.request.urlopen(request, context=self.ssl_context, timeout=30) as response:
                # Read the PDF content
                pdf_content = response.read()
                
                # Verify it's actually a PDF
                if not pdf_content.startswith(b'%PDF'):
                    raise ValueError("Downloaded file is not a valid PDF")
                
                # Write to file
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
            
            logger.info(f"Successfully downloaded PDF to {output_path}")
            return output_path
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(f"Paper {arxiv_id} not found on ArXiv")
            else:
                raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e.reason}")
        except Exception as e:
            logger.error(f"Download failed for {arxiv_id}: {e}")
            raise
    
    def download_from_url(self, url: str, output_path: str) -> str:
        """
        Download a PDF from any URL.
        
        Args:
            url: URL to download from
            output_path: Path to save the PDF
            
        Returns:
            Path to downloaded PDF
        """
        logger.info(f"Downloading PDF from {url}")
        
        try:
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            with urllib.request.urlopen(request, context=self.ssl_context, timeout=30) as response:
                pdf_content = response.read()
                
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
            
            logger.info(f"Successfully downloaded PDF to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Download failed from {url}: {e}")
            raise