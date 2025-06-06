import re
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io
import cv2
import numpy as np

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class DataExtractor:
    def __init__(self):
        self.patterns = {
            'AL Number': [
                r'AL\s*Number\s*:?\s*([A-Z0-9\-/]+)',
                r'Authorization\s*Letter\s*Number\s*:?\s*([A-Z0-9\-/]+)',
                r'AL\s*No\s*:?\s*([A-Z0-9\-/]+)',
                r'AL\s*ID\s*:?\s*([A-Z0-9\-/]+)',
                r'AL\s*:?\s*([A-Z0-9\-/]+)'
            ],
            'Approved Amount': [
                r'Approved\s*Amount\s*:?\s*[Rs\.\s]*(\d+)',
                r'Final\s*Approved\s*Amount\s*:?\s*(\d+)',
                r'Sanctioned\s*Amount\s*:?\s*(\d+)'
            ],
            'Date of Admission': [
                r'Date\s*of\s*Admission\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*)',
                r'Admission\s*Date\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*)'
            ],
            'Date of Discharge': [
                r'Date\s*of\s*Discharge\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*)',
                r'Discharge\s*Date\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*)'
            ],
            'Name of the Patient': [
                r'Name\s*of\s*Patient\s*:?\s*([A-Z][a-zA-Z\s]+)(?=\s*UHID|\s*Age|\s*Gender)',
                r'Patient\s*Name\s*:?\s*([A-Z][a-zA-Z\s]+)'
            ],
            'Policy No': [
                r'Policy\s*No\s*:?\s*([A-Z0-9\/\-]+)',
                r'Policy\s*Number\s*:?\s*([A-Z0-9\/\-]+)'
            ],
            'Policy Period': [
                r'Policy\s*Period\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*)',
                r'Policy\s*Term\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*)'
            ],
            'Total Bill Amount': [
                r'Total\s*Bill\s*Amount\s*:?\s*(\d+)',
                r'Bill\s*Amount\s*:?\s*(\d+)'
            ],
            'UHID Number': [
                r'UHID\s*Number\s*:?\s*([A-Z0-9]+)',
                r'UHID\s*:?\s*([A-Z0-9]+)'
            ],
            'Remarks': [
                r'Remarks\s*:?\s*(.*?)(?=\n\s*[A-Z][a-z]+\s*:|$)'
            ]
        }

    def preprocess_image(self, img):
        """Simpler image preprocessing"""
        try:
            # Convert to numpy array
            img_np = np.array(img)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            
            # Simple thresholding
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            
            return Image.fromarray(thresh)
        except Exception as e:
            print(f"Preprocessing error: {e}")
            return img

    def extract_text_from_pdf(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # First try to extract text directly
                page_text = page.get_text()
                
                # If no text or very little text, use OCR
                if len(page_text.strip()) < 50:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Simple preprocessing
                    processed_img = self.preprocess_image(img)
                    
                    # Try with different OCR configurations
                    try:
                        # First try with default config
                        ocr_text = pytesseract.image_to_string(processed_img)
                        
                        # If not enough text, try with different PSM
                        if len(ocr_text.strip()) < 50:
                            ocr_text = pytesseract.image_to_string(
                                processed_img, 
                                config='--psm 6 -c preserve_interword_spaces=1'
                            )
                        
                        page_text = ocr_text
                    except Exception as e:
                        print(f"OCR error: {e}")
                        continue
                
                text += page_text + "\n\n"
            
            doc.close()
            return text
        
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""

    def clean_extracted_value(self, value, field_name):
        if not value:
            return None
        
        value = value.strip()
        
        # Common cleaning for all fields
        value = re.sub(r'\s+', ' ', value)  # Replace multiple spaces with single
        
        if field_name == 'Name of the Patient':
            # Remove any special characters except spaces and dots
            value = re.sub(r'[^a-zA-Z\s\.]', '', value)
            value = value.title()
            return value if len(value.split()) >= 2 else None
        
        elif field_name in ['Date of Admission', 'Date of Discharge', 'Policy Period']:
            # Fix common OCR errors in dates
            value = value.replace('o', '0').replace('O', '0')
            value = re.sub(r'[^\w\s-]', '-', value)  # Standardize separators
            return value.upper() if any(c.isdigit() for c in value) else None
        
        elif field_name in ['Approved Amount', 'Total Bill Amount']:
            # Extract first number found
            numbers = re.findall(r'\d+', value)
            return numbers[0] if numbers else None
        
        elif field_name in ['AL Number', 'Policy No', 'UHID Number']:
            # Remove special characters but keep allowed ones
            if field_name == 'AL Number':
                allowed_chars = r'A-Z0-9\-/'
            elif field_name == 'Policy No':
                allowed_chars = r'A-Z0-9\/\-'
            else:  # UHID Number
                allowed_chars = r'A-Z0-9'
            
            value = re.sub(f'[^{allowed_chars}]', '', value.upper())
            return value if len(value) >= 3 else None
        
        elif field_name == 'Remarks':
            # Just clean up whitespace
            return value.strip()
        
        return value

    def extract_field(self, text, field_name):
        patterns = self.patterns.get(field_name, [])
        
        for pattern in patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    # Get the first matching group from the first match
                    value = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    cleaned = self.clean_extracted_value(value, field_name)
                    if cleaned:
                        return cleaned
            except Exception as e:
                print(f"Error extracting {field_name}: {e}")
                continue
        
        return None

    def extract_all_data(self, pdf_path):
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text.strip():
            print("No text could be extracted from the PDF")
            return None
        
        print("=== Extracted Text ===")  # Debug print
        print(text[:1000])  # Print first 1000 chars for debugging
        print("=====================")
        
        extracted_data = {}
        for field_name in self.patterns.keys():
            extracted_data[field_name] = self.extract_field(text, field_name)
        
        extracted_data['Letter Type'] = 'Authorization Letter'
        return extracted_data

    def process_pdf(self, pdf_path):
        try:
            if not Path(pdf_path).exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            data = self.extract_all_data(pdf_path)
            
            if data:
                return {
                    "AL Number": data.get('AL Number'),
                    "Approved Amount": data.get('Approved Amount'),
                    "Date of Admission": data.get('Date of Admission'),
                    "Date of Discharge": data.get('Date of Discharge'),
                    "Letter Type": data.get('Letter Type'),
                    "Name of the Patient": data.get('Name of the Patient'),
                    "Policy No": data.get('Policy No'),
                    "Policy Period": data.get('Policy Period'),
                    "Remarks": data.get('Remarks'),
                    "Total Bill Amount": data.get('Total Bill Amount'),
                    "UHID Number": data.get('UHID Number')
                }
            return None
        
        except Exception as e:
            print(f"Error processing PDF: {e}")
            return None

def main():
    if len(sys.argv) == 2:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "pdf1.pdf"
        print(f"No command line argument provided, using default: {pdf_path}")

    extractor = DataExtractor()
    result = extractor.process_pdf(pdf_path)

    if result:
        print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print("Failed to extract data from PDF")
        sys.exit(1)

if __name__ == "__main__":
    main()