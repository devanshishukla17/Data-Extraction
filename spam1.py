import re
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import io
import pytesseract

class DenialLetterExtractor:
    def __init__(self):
        pass

    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using PyMuPDF with fallback to OCR if needed"""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            for page in doc:
                page_text = page.get_text()
                
                if not page_text.strip():
                    # Fallback to OCR if no text found
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    page_text = pytesseract.image_to_string(img, config='--psm 4')
                
                text += page_text + "\n"
            
            doc.close()
            return text
            
        except Exception as e:
            print(f"Error extracting text from PDF: {e}", file=sys.stderr)
            return ""

    def extract_address_layout(self, pdf_path):
        """Extract address using spatial layout analysis"""
        try:
            doc = fitz.open(pdf_path)
            page = doc[0]  # First page
            words = page.get_text("words")
            
            address_lines = []
            start_y = None
            end_y = None
            stop_processing = False

            # Find "To,"
            for w in words:
                if w[4].strip() == 'To,':  # w[4] is the text in PyMuPDF
                    start_y = w[3]  # w[3] is bottom coordinate
                    break
            if start_y is None:
                return "null"

            # Find end marker (Subject or other indicators)
            for w in words:
                if w[4].strip().startswith('Subject') and w[3] > start_y:
                    end_y = w[1]  # w[1] is top coordinate
                    break
            if end_y is None:
                end_y = start_y + 150

            lines = {}
            for w in words:
                # Stop processing if we hit certain markers
                if 'Inlias' in w[4] or ('ID' in w[4] and ':' in w[4]):
                    stop_processing = True
                    continue
                    
                if stop_processing:
                    continue
                    
                if start_y < w[1] < end_y and w[0] < 250:  # w[0] is x0, w[1] is y0
                    y = round(w[1], 1)
                    lines.setdefault(y, []).append(w[4])

            sorted_lines = [lines[y] for y in sorted(lines)]
            full_lines = [' '.join(line) for line in sorted_lines]
            
            # Join and clean the address
            address = ', '.join(full_lines)
            
            # Final cleanup to remove any trailing commas or spaces
            address = address.rstrip(', ')
            
            return address if address else "null"
            
        except Exception as e:
            print(f"Error extracting address layout: {e}", file=sys.stderr)
            return "null"
        finally:
            if 'doc' in locals():
                doc.close()

    def extract_al_number(self, text):
        """Extract AL Number from the line containing 'AL No :'"""
        try:
            match = re.search(r'AL\s*No\s*:\s*([^\s]+)', text)
            return match.group(1) if match else None
        except Exception as e:
            print(f"Error extracting AL Number: {e}", file=sys.stderr)
            return None

    def extract_patient_name(self, text):
        """Extract patient name after 'Subject :- Denial of Pre-Auth for'"""
        try:
            match = re.search(r'Subject\s*:-\s*Denial\s*of\s*Pre-Auth\s*for\s*([^\n]+)', text)
            return match.group(1).strip() if match else None
        except Exception as e:
            print(f"Error extracting patient name: {e}", file=sys.stderr)
            return None

    def extract_table_values(self, text):
        """Extract values from the table (Member ID and Policy Number)"""
        try:
            # Find the table section
            table_section = re.search(r'Member ID\s*\|.*?Policy Number\s*\|.*?\n(.*?)\n', text, re.DOTALL)
            if not table_section:
                return None, None
            
            # Extract all values from the table row
            values = re.findall(r'\|\s*([^\|]+)\s*\|', table_section.group(0))
            if len(values) >= 4:
                member_id = values[0].strip()
                policy_number = values[3].strip()
                return member_id, policy_number
            return None, None
        except Exception as e:
            print(f"Error extracting table values: {e}", file=sys.stderr)
            return None, None

    def process_denial_letter(self, pdf_path):
        """Process the denial letter PDF and extract all required fields"""
        text = self.extract_text_from_pdf(pdf_path)
        if not text.strip():
            return None

        # Extract all fields
        hospital_address = self.extract_address_layout(pdf_path)
        al_number = self.extract_al_number(text)
        patient_name = self.extract_patient_name(text)
        member_id, policy_number = self.extract_table_values(text)

        return {
            "AL Number": al_number,
            "UHID Number": member_id,
            "Name of the Patient": patient_name,
            "Policy Number": policy_number,
            "Hospital Address": hospital_address,
            "Reason": None  # To be implemented later
        }

def main():
    if len(sys.argv) != 2:
        print("Usage: python denial_extractor.py <path_to_pdf>", file=sys.stderr)
        sys.exit(1)

    extractor = DenialLetterExtractor()
    result = extractor.process_denial_letter(sys.argv[1])

    if result:
        print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print("Failed to extract data from denial letter", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    main()