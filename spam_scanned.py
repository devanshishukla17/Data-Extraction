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
                r'Authorization\s*Letter\s*Number\s*:?\s*([A-Z0-9\-/]+)'
            ],
            'Approved Amount': [
                r'Final\s*Amount\s*Sanctioned\s*:?\s*Rs\.?\s*(\d+)',
                r'guarantee\s*for\s*payment\s*of\s*Rs\s*(\d+)',
                r'Approved\s*Amount\s*:?\s*Rs\.?\s*(\d+)'
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
                r'Name\s*of\s*the\s*Patient\s*:?\s*([A-Z][a-zA-Z\s]+)(?=\s*UHID|\s*Policy)',
                r'Patient\s*Name\s*:?\s*([A-Z][a-zA-Z\s]+)'
            ],
            'Policy No': [
                r'Policy\s*No\s*:?\s*([A-Z0-9\/\-]+)',
                r'Policy\s*Number\s*:?\s*([A-Z0-9\/\-]+)'
            ],
            'Policy Period': [
                r'Policy\s*Period\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*\s*To\s*[\d-]+[A-Za-z]{3,}[-\d]*)',
                r'Policy\s*Term\s*:?\s*([\d-]+[A-Za-z]{3,}[-\d]*\s*To\s*[\d-]+[A-Za-z]{3,}[-\d]*)'
            ],
            'Total Bill Amount': [
                r'Total\s*Bill\s*Amount\s*:?\s*(\d+)',
                r'Bill\s*Amount\s*:?\s*(\d+)',
                r'Final\s*Requested\s*Amount\s*:?\s*Rs\.?\s*(\d+)'
            ],
            'UHID Number': [
                r'UHID\s*Number\s*:?\s*([A-Z0-9]+)',
                r'UHID\s*:?\s*([A-Z0-9]+)'
            ],
            'Remarks': [
                r'Remarks\s*:?\s*(.*?)(?=\n\s*[A-Z][a-z]+\s*:|$)',
                r'Remarks\s*:?\s*(.*?)(?=\n\s*For\s+any\s+cashless)'
            ]
        }

    def preprocess_image(self, img):
        try:
            img_np = np.array(img)
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            
            scale_percent = 200  
            width = int(gray.shape[1] * scale_percent / 100)
            height = int(gray.shape[0] * scale_percent / 100)
            dim = (width, height)
            resized = cv2.resize(gray, dim, interpolation=cv2.INTER_CUBIC)
            
            thresh = cv2.adaptiveThreshold(resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY, 11, 2)
       
            kernel = np.ones((1, 1), np.uint8)
            processed = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            
            return Image.fromarray(processed)
        except Exception as e:
            print(f"Preprocessing error: {e}")
            return img

    def extract_text_from_pdf(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
            
                page_text = page.get_text()
                
        
                if len(page_text.strip()) < 100 or "Name of the Patient" not in page_text:
                    zoom = 4 
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    processed_img = self.preprocess_image(img)
                    custom_config = r'--oem 3 --psm 4 -c preserve_interword_spaces=1'
                    page_text = pytesseract.image_to_string(processed_img, config=custom_config)
                
                full_text += page_text + "\n\n"
            
            doc.close()
            return full_text
        
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""

    def clean_extracted_value(self, value, field_name):
        if not value:
            return None
        
        value = value.strip()
        value = re.sub(r'\s+', ' ', value)  
        
        if field_name == 'Name of the Patient':
            value = re.sub(r'[^a-zA-Z\s\.]', '', value)
            value = value.title()
            return value if len(value.split()) >= 2 else None
        
        elif field_name in ['Date of Admission', 'Date of Discharge']:
            value = value.replace('o', '0').replace('O', '0')
            value = re.sub(r'[^\w\s-]', '-', value)  
            month_map = {
                'JAN': 'JAN', 'FEB': 'FEB', 'MAR': 'MAR',
                'APR': 'APR', 'MAY': 'MAY', 'JUN': 'JUN',
                'JUL': 'JUL', 'AUG': 'AUG', 'SEP': 'SEP',
                'OCT': 'OCT', 'NOV': 'NOV', 'DEC': 'DEC'
            }
            for wrong, correct in month_map.items():
                value = value.replace(wrong.upper(), correct)
            
            return value.upper() if any(c.isdigit() for c in value) else None
        
        elif field_name == 'Policy Period':
            value = value.replace('To', 'to').replace('TO', 'to')
            value = re.sub(r'[^\w\s-to]', '-', value)
            return value if any(c.isdigit() for c in value) else None
        
        elif field_name in ['Approved Amount', 'Total Bill Amount']:
            numbers = re.findall(r'\d+', value.replace(',', ''))
            return numbers[0] if numbers else None
        
        elif field_name in ['AL Number', 'Policy No', 'UHID Number']:

            if field_name == 'AL Number':
                allowed = r'A-Z0-9\-/'
            elif field_name == 'Policy No':
                allowed = r'A-Z0-9\/\-'
            else:  
                allowed = r'A-Z0-9'
            
            value = re.sub(f'[^{allowed}]', '', value.upper())
            return value if len(value) >= 3 else None
        
        elif field_name == 'Remarks':
            return value.strip()
        
        return value

    def extract_field(self, text, field_name):
        patterns = self.patterns.get(field_name, [])
        
        for pattern in patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    value = match.group(1).strip()
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
        
        print("=== Extracted Text Sample ===")
        print(text[:1000] + ("..." if len(text) > 1000 else ""))
        print("============================")
        
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
        pdf_path = "img_pdf1.pdf"  
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