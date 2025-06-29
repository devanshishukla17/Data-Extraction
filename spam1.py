# import pdfplumber
# import re
# import json
# import sys

# def suppress_warnings():
#     # Suppress the CropBox warnings
#     import warnings
#     warnings.filterwarnings("ignore", message="CropBox missing from /Page, defaulting to MediaBox")

# def extract_hospital_address(page):
#     words = page.extract_words()
#     address_lines = []
#     start_y = None
#     end_y = None

#     # Look for the hospital name which appears just before the address
#     for i, w in enumerate(words):
#         if "HOSPITAL" in w['text'].upper():
#             start_y = w['top']
#             break
    
#     if start_y is None:
#         return "null"

#     # Find the end of the address (before the city name repeats)
#     for w in words[i+1:]:
#         if w['text'].strip().isdigit() and len(w['text'].strip()) == 6:  # PIN code detection
#             end_y = w['top'] + 20
#             break
#     if end_y is None:
#         end_y = start_y + 150

#     lines = {}
#     for w in words:
#         if start_y < w['top'] < end_y and w['x0'] < 250:
#             y = round(w['top'], 1)
#             lines.setdefault(y, []).append(w['text'])

#     sorted_lines = [lines[y] for y in sorted(lines)]
#     full_lines = [' '.join(line) for line in sorted_lines]
#     return ', '.join(full_lines).replace(',,', ',')

# def extract_info_from_pdf(pdf_path):
#     suppress_warnings()
    
#     extracted_data = {
#         "AL Number": "null",
#         "Approved Amount": "null",
#         "Date & Time": "null",
#         "Date of Admission": "null",
#         "Date of Discharge": "null",
#         "Hospital Address": "null",
#         "Letter Type": "Approval",
#         "Name of the Patient": "null",
#         "Policy No": "null",
#         "Policy Period": "null",
#         "Remarks": "null",
#         "Total Bill Amount": "null",
#         "UHID Number": "null"
#     }
     
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             page = pdf.pages[0]
#             text = page.extract_text()

#             # Extract Hospital Address
#             extracted_data["Hospital Address"] = extract_hospital_address(page)
            
#             # Extract AL Number (Claim Number)
#             al_match = re.search(r"Claim Number AL:\s*([^\s\n]+)", text)
#             if al_match:
#                 extracted_data["AL Number"] = al_match.group(1).strip('()')
            
#             # Extract Patient Name
#             patient_match = re.search(r"Patient Name\s*:\s*([^\n]+?)(?=\s*Age\s*:|$)", text)
#             if patient_match:
#                 extracted_data["Name of the Patient"] = patient_match.match.group(1).strip()
            
#             # Extract Policy Number
#             policy_match = re.search(r"Policy No\s*:\s*([A-Za-z0-9\/-]+)", text)
#             if policy_match:
#                 extracted_data["Policy No"] = policy_match.group(1).strip()
            
#             # Extract Policy Period
#             period_match = re.search(r"Policy period\s*:\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})", text, re.IGNORECASE)
#             if period_match:
#                 extracted_data["Policy Period"] = f"{period_match.group(1).strip()} To {period_match.group(2).strip()}"
            
#             # Extract Dates
#             admission_match = re.search(r"Expected Date of Admission\s*:\s*(\d{2}-\w{3}-\d{4})", text)
#             if admission_match:
#                 extracted_data["Date of Admission"] = admission_match.group(1).strip()
            
#             discharge_match = re.search(r"Expected Date of Discharge\s*:\s*(\d{2}-\w{3}-\d{4})", text)
#             if discharge_match:
#                 extracted_data["Date of Discharge"] = discharge_match.group(1).strip()
            
#             # Extract Authorization Details
#             auth_match = re.search(r"Authorization Details:\s*(\d{2}/\w{3}/\d{4}\s+\d{1,2}:\d{2}:\d{2})\s+([^\s]+)\s+([\d,]+\.\d{2})", text)
#             if auth_match:
#                 extracted_data["Date & Time"] = auth_match.group(1).strip()
#                 extracted_data["Approved Amount"] = auth_match.group(3).strip()
            
#             # Extract Remarks
#             remarks_match = re.search(r"Authorization remarks\s*:\s*(.*?)(?:\n\n|\n\*|$)", text, re.DOTALL | re.IGNORECASE)
#             if remarks_match:
#                 extracted_data["Remarks"] = remarks_match.group(1).strip()
            
#             # Extract Total Bill Amount
#             bill_match = re.search(r"Total Bill Amount\s*([\d,]+\.\d{2})", text)
#             if bill_match:
#                 extracted_data["Total Bill Amount"] = bill_match.group(1).strip()
            
#             # Extract UHID Number (assuming this is the Rohini ID)
#             uhid_match = re.search(r"Rohini ID\s*:\s*([^\s\n]+)", text)
#             if uhid_match:
#                 extracted_data["UHID Number"] = uhid_match.group(1).strip()

#     except Exception as e:
#         print(f"Error processing PDF: {str(e)}", file=sys.stderr)

#     return extracted_data

# if __name__ == "__main__":
#     if len(sys.argv) != 2:
#         print("Usage: python script.py <path_to_pdf>")
#         sys.exit(1)

#     result = extract_info_from_pdf(sys.argv[1])
#     print(json.dumps(result, indent=4))

#---------------------------------------------------------------------------------------------------------------------

import re
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io
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
                r'Final\s+(?:Sanctioned|Approved)\s+Amount\s*:?\s*(\d+)',
                r'Amount\s+(?:to\s+be\s+)?(?:sanctioned|approved)\s*:?\s*[Rs\.\s]*(\d+)',
                r'guarantee\s+for\s+payment\s+of\s+Rs\s*(\d+)',
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
                r'Bill\s+Amount\s*:\s*([\d,]+\.\d{2})'
            ],
            'UHID Number': [
                r'Insurer\s+Id\s+of\s+the\s+Patient\s*:\s*([A-Z0-9]+)',
                r'Insurer\s+ID\s*:\s*([A-Z0-9]+)',
                r'Patient\s+ID\s*:\s*([A-Z0-9]+)'
            ],
            'Remarks': [
                r'Authorization\s+remarks\s*:\s*(.*?)(?=\n\n|\n\*|$)',
                r'Remarks\s*:\s*(.*?)(?=\n\n|\n\*|$)'
            ]
        }
    
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
        
        # Handle tuple values (like Policy Period or multi-line names)
        if isinstance(value, tuple):
            if field_name == 'Policy Period':
                return f"{value[0].strip()} To {value[1].strip()}"
            elif field_name == 'Name of the Patient':
                # Combine both lines of the name and clean
                combined = ' '.join([v.strip() for v in value if v.strip()])
                # Remove any trailing Age information
                combined = re.sub(r'\s*Age\s*:.*$', '', combined)
                return combined.strip()
            return None
        
        value = str(value).strip()

        if field_name == 'Name of the Patient':
            # Remove any Age information or other trailing details
            value = re.sub(r'\s*Age\s*:.*$', '', value)
            value = ' '.join(value.split())
            return value if len(value) > 2 else None
        
        elif field_name in ['Date of Admission', 'Date of Discharge']:
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
        
        extracted_data['Letter Type'] = 'Authorization Letter'
        
        return extracted_data
    
    def process_pdf(self, pdf_path):
        try:
            if not Path(pdf_path).exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Extract text first and store it
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
                    "Remarks": data.get('Remarks'),
                    "Total Bill Amount": data.get('Total Bill Amount'),
                    "Approved Amount": data.get('Approved Amount'),
                    "Hospital Address": data.get('Hospital Address')
                }
                
                # Final validation for patient name with access to text
                if not formatted_data["Name of the Patient"] or len(formatted_data["Name of the Patient"].split()) < 2:
                    # Try multi-line pattern first
                    alt_match = re.search(r'Patient\s*Name\s*:\s*([^\n]+?)\n([^\n]+?)(?=\nAge\s*:|$)', text, re.DOTALL)
                    if alt_match:
                        name = ' '.join([alt_match.group(1).strip(), alt_match.group(2).strip()])
                        name = re.sub(r'\s*Age\s*:.*$', '', name)
                        formatted_data["Name of the Patient"] = name.strip()
                    else:
                        # Fall back to single line pattern
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