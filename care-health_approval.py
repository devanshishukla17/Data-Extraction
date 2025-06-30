import re
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import io
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class DataExtractor:
    def __init__(self):
        self.patterns = {
            'AL Number': [
                r'AL\s*Number\s*:?\s*([^\s]+)',  
                r'AL\s*:?\s*([^\s]+)',
                r'Authorization\s+Letter\s+Number\s*:?\s*([^\s]+)'
            ],
            'Approved Amount': [
                r'Total\s+Authorized\s+Amount\s*:\s*([\d,]+\.\d{2})',
                r'Total\s+Authorized\s+Amount\s*\|\s*([\d,]+\.\d{2})',
                r'Final\s+(?:Sanctioned|Approved)\s+Amount\s*:?\s*(\d+)',
                r'Sanctioned\s+Amount\s*:?\s*(\d+)'
            ],
            'Date of Admission': [
                r'Expected\s+Date\s+of\s+Admission\s*:\s*(\d{2}-\w{3}-\d{4})',
                r'Date\s+of\s+Admission\s*:\s*(\d{2}-\w{3}-\d{4})'
            ],
            'Date of Discharge': [
                r'Expected\s+Date\s+of\s+Discharge\s*:\s*(\d{2}-\w{3}-\d{4})',
                r'Date\s+of\s+Discharge\s*:\s*(\d{2}-\w{3}-\d{4})'
            ],
            'Name of the Patient': [
                r'Patient\s*Name\s*:\s*([^\n]+?)\n([^\n]+?)(?=\nAge\s*:|$)',
                r'Name\s+of\s+Patient\s*:\s*([^\n]+?)\n([^\n]+?)(?=\nAge\s*:|$)',
                r'Patient\s*Name\s*:\s*([^\n]+?)(?=\s*Age\s*:|$)',
                r'Name\s+of\s+Patient\s*:\s*([^\n]+?)(?=\s*Age\s*:|$)'
            ],
            'Policy No': [
                r'Policy\s+No\s*:\s*([A-Z0-9\/\-]+)',
                r'Policy\s+Number\s*:\s*([A-Z0-9\/\-]+)'
            ],
            'Policy Period': [
                r'Policy\s*period\s*:\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})',
                r'Policy\s+Period\s*:\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})',
                r'Policy\s+Term\s*:\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})'
            ],
            'Total Bill Amount': [
                r'Total\s+Bill\s+Amount\s*:\s*([\d,]+\.\d{2})',
                r'Total\s+Bill\s+Amount\s*\|\s*([\d,]+\.\d{2})',
                r'Bill\s+Amount\s*:\s*([\d,]+\.\d{2})'
            ],
            'UHID Number': [
                r'Insurer\s+Id\s+of\s+the\s+Patient\s*:\s*([A-Z0-9]+)',
                r'Insurer\s+ID\s*:\s*([A-Z0-9]+)',
                r'Patient\s+ID\s*:\s*([A-Z0-9]+)'
            ],
            'Remarks': [
                r'Authorization\s+remarks\s*:\s*(.*?)(?=\s*Hospital\s+Agreed\s+Tariff\s*:|$)',
                r'Remarks\s*:\s*(.*?)(?=\n\n|\n\*|$)'
            ],
            'Date & Time': [
                r'Authorization\s+Details:.*?\n\|.*?\n\|(.*?)\n.*?Total'
            ]
        }
    
    def extract_hospital_address(self, page):
        words = page.get_text("words")
        address_lines = []
        start_y = None
        end_y = None

        for i, w in enumerate(words):
            if "HOSPITAL" in w[4].upper():  
                start_y = w[3]  
                break
        
        if start_y is None:
            return None

        for w in words[i+1:]:
            if w[4].strip().isdigit() and len(w[4].strip()) == 6: 
                end_y = w[3] + 20  
                break
        if end_y is None:
            end_y = start_y + 150  

        lines = {}
        for w in words:
            if start_y < w[1] < end_y and w[0] < 250:  
                y = round(w[1], 1) 
                lines.setdefault(y, []).append(w[4])

        sorted_lines = [lines[y] for y in sorted(lines)]
        full_lines = [' '.join(line) for line in sorted_lines]
        return ', '.join(full_lines).replace(',,', ',')
    
    def extract_text_from_pdf(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                
                if not page_text.strip():
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    page_text = pytesseract.image_to_string(img, config='--psm 4')
                
                text += page_text + "\n"
            
            doc.close()
            return text
            
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""
    
    def clean_extracted_value(self, value, field_name):
        if not value:
            return None
        
        if isinstance(value, tuple):
            if field_name == 'Policy Period':
                return f"{value[0].strip()} To {value[1].strip()}"
            elif field_name == 'Name of the Patient':
                combined = ' '.join([v.strip() for v in value if v.strip()])
                combined = re.sub(r'\s*Age\s*:.*$', '', combined)
                return combined.strip()
            return None
        
        value = str(value).strip()

        if field_name == 'Name of the Patient':
            value = re.sub(r'\s*Age\s*:.*$', '', value)
            value = ' '.join(value.split())
            return value if len(value) > 2 else None
        
        elif field_name in ['Date of Admission', 'Date of Discharge', 'Date & Time']:
            return value
        
        elif field_name in ['Approved Amount', 'Total Bill Amount']:
            return value.replace(',', '')
        
        elif field_name == 'Policy Period':
            value = re.sub(r'\s+', ' ', value)
            return value
        
        elif field_name == 'Remarks':
            value = re.sub(r'\s+', ' ', value)
            value = re.sub(r'^(Remarks?\s*:?\s*)', '', value, flags=re.IGNORECASE)
            return value.strip()
        
        elif field_name == 'AL Number':
            return value.split('(')[0].strip() if '(' in value else value.strip()
        
        return value
    
    def extract_field(self, text, field_name):
        if field_name == 'Date & Time':
            auth_section = re.search(r'Authorization\s+Details:(.*?)(?:\n\n|\Z)', text, re.DOTALL | re.IGNORECASE)
            if auth_section:
                section_text = auth_section.group(1)
                date_matches = re.findall(
                    r'(\d{2}/[a-zA-Z]{3}/\d{4}\s+\d{2}:\d{2}:\d{2})',
                    section_text,
                    re.IGNORECASE
                )
                if date_matches:
                    return date_matches[-1]
            return None

        if field_name == 'Remarks':
            remarks_match = re.search(
                r'Authorization\s+remarks\s*:\s*(.*?)(?=\s*Hospital\s+Agreed\s+Tariff\s*:|$)', 
                text, 
                re.DOTALL | re.IGNORECASE
            )
            if remarks_match:
                return remarks_match.group(1).strip()
            for pattern in self.patterns.get('Remarks', []):
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    return matches[0]
            return None

        if field_name in ['Total Bill Amount', 'Approved Amount']:
            non_package_section = re.search(r'II\.\s*Non\s*Package\s*Case.*?Authorization\s*Summary:(.*?)(?:\n\n|\Z)', text, re.DOTALL | re.IGNORECASE)
            if non_package_section:
                section_text = non_package_section.group(1)
                if field_name == 'Total Bill Amount':
                    bill_match = re.search(r'Total\s+Bill\s+Amount\s*[:\|]?\s*([\d,]+\.\d{2})', section_text)
                    if bill_match:
                        return bill_match.group(1)
                elif field_name == 'Approved Amount':
                    approved_match = re.search(r'Total\s+Authorized\s+Amount\s*[:\|]?\s*([\d,]+\.\d{2})', section_text)
                    if approved_match:
                        return approved_match.group(1)

        patterns = self.patterns.get(field_name, [])
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                match = matches[0]
                return match
        
        return None
        
    def extract_all_data(self, pdf_path):        
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text.strip():
            print("No text could be extracted from the PDF")
            return None

        extracted_data = {}
        for field_name in self.patterns.keys():
            value = self.extract_field(text, field_name)
            extracted_data[field_name] = self.clean_extracted_value(value, field_name)
        
        try:
            doc = fitz.open(pdf_path)
            page = doc.load_page(0)  
            extracted_data['Hospital Address'] = self.extract_hospital_address(page)
            doc.close()
        except Exception as e:
            print(f"Error extracting hospital address: {e}")
            extracted_data['Hospital Address'] = None
        
        extracted_data['Letter Type'] = 'Approval Letter'
        
        return extracted_data
    
    def process_pdf(self, pdf_path):
        try:
            if not Path(pdf_path).exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")

            text = self.extract_text_from_pdf(pdf_path)
            if not text.strip():
                return None
                
            data = self.extract_all_data(pdf_path)
            
            if data:
                formatted_data = {
                    "Letter Type": data.get('Letter Type'),
                    "AL Number": data.get('AL Number'),
                    "UHID Number": data.get('UHID Number'),
                    "Name of the Patient": data.get('Name of the Patient'),
                    "Policy No": data.get('Policy No'),
                    "Policy Period": data.get('Policy Period'),
                    "Date of Admission": data.get('Date of Admission'),
                    "Date of Discharge": data.get('Date of Discharge'),
                    "Date & Time": data.get('Date & Time'), 
                    "Remarks": data.get('Remarks'),
                    "Total Bill Amount": data.get('Total Bill Amount'),
                    "Approved Amount": data.get('Approved Amount'),
                    "Hospital Address": data.get('Hospital Address')
                }
                
                if not formatted_data["Name of the Patient"] or len(formatted_data["Name of the Patient"].split()) < 2:
                    alt_match = re.search(r'Patient\s*Name\s*:\s*([^\n]+?)\n([^\n]+?)(?=\nAge\s*:|$)', text, re.DOTALL)
                    if alt_match:
                        name = ' '.join([alt_match.group(1).strip(), alt_match.group(2).strip()])
                        name = re.sub(r'\s*Age\s*:.*$', '', name)
                        formatted_data["Name of the Patient"] = name.strip()
                    else:
                        alt_match = re.search(r'Patient\s*Name\s*:\s*([^\n]+?)(?=\s*Age\s*:|$)', text, re.DOTALL)
                        if alt_match:
                            name = alt_match.group(1).strip()
                            name = re.sub(r'\s*Age\s*:.*$', '', name)
                            formatted_data["Name of the Patient"] = name.strip()
                
                return formatted_data
            else:
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