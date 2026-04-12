"""
report_parsing.py — Text/Image extraction utility for Medical Report Reader
"""

import base64
import logging
from typing import List

logger = logging.getLogger(__name__)

def convert_bytes_to_base64_images(file_bytes: bytes, filename: str) -> List[str]:
    """
    Takes raw file bytes and a filename.
    If it's an image (jpg/png), simply base64 encodes it.
    If it's a PDF, uses PyMuPDF to render pages as images and encodes them.
    
    Returns a list of base64 encoded image strings ready for GPT-4o Vision.
    """
    ext = filename.lower().split('.')[-1]
    
    if ext in ['png', 'jpg', 'jpeg', 'webp']:
        # Direct encode
        return [base64.b64encode(file_bytes).decode('utf-8')]
        
    elif ext == 'pdf':
        try:
            import fitz # PyMuPDF
            images_b64 = []
            
            # Open the PDF from memory
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            # Limit to first 5 pages for cost/token limits if needed
            max_pages = min(len(doc), 5)
            
            # Use appropriate resolution (zoom = 2 for better legibility)
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            
            for page_num in range(max_pages):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                # Convert straight to binary PNG format
                img_bytes = pix.tobytes("png")
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                images_b64.append(b64)
                
            doc.close()
            return images_b64
            
        except Exception as e:
            logger.error("report_parsing: Error extracting PDF images: %s", e)
            return []
            
    else:
        logger.warning("report_parsing: Unsupported file type '%s'", ext)
        return []
