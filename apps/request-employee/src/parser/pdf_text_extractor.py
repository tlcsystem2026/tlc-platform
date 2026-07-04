from pathlib import Path
import pdfplumber

class PDFTextExtractor:
    def extract(self,pdf_path:str)->str:
        text=[]
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
