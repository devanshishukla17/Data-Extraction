import re
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\DEVANSHI\tesseract.exe"

class DataExtractor:
    def __init__(self):
        self.patterns = {
            'AL Number': [
                r'AL\s+Number\s*:?\s*([A-Z0-9\-/]+)',
                r'Authorization\s+Letter\s+Number\s*:?\s*([A-Z0-9\-/]+)',
                r'AL\s+No\s*:?\s*([A-Z0-9\-/]+)',
                r'AL\s+ID\s*:?\s*([A-Z0-9\-/]+)',
                r'AL\s*:?\s*([A-Z0-9\-/]+)'
            ],
            'Approved Amount': [
                r'Final\s+(?:Sanctioned|Approved)\s+Amount\s*:?\s*(\d+)',
                r'Amount\s+(?:to\s+be\s+)?(?:sanctioned|approved)\s*:?\s*[Rs\.\s]*(\d+)',
                r'guarantee\s+for\s+payment\s+of\s+Rs\s*(\d+)',
                r'Sanctioned\s+Amount\s*:?\s*(\d+)'
            ],
            'Date of Admission': [
                r'Date\s+of\s+Admission\s*:?\s*([^\n:]*?(?:2025|25))'
            ],
            'Date of Discharge': [
                r'Date\s+of\s+Discharge\s*:?\s*([^\n:]*?(?:2025|25))',
                r'Discharge\s+Date\s*:?\s*([^\n:]*?(?:2025|25))'
            ],
            'Name of the Patient': [
                r'Name\s+of\s+(?:the\s+)?Patient\s*:?\s*([A-Z][a-zA-Z\s\.]{2,50})(?=\s+UHID|\s+Age|\s+Gender)',
                r'Patient\s+Name\s*:?\s*([A-Z][a-zA-Z\s\.]{2,50})(?=\s+UHID|\s+Age|\s+Gender)',
                r'Patient\s*:?\s*([A-Z][a-zA-Z\s\.]{2,50})(?=\s+UHID|\s+Age|\s+Gender)'
            ],
            'Policy No': [
                r'Policy\s+No\s*:?\s*([A-Z0-9\/\-]+)',
                r'Policy\s+Number\s*:?\s*([A-Z0-9\/\-]+)'
            ],
            'Policy Period': [
                r'Policy\s+Period\s*:?\s*([^:\n]*?(?:2025|25))',
                r'Policy\s+Term\s*:?\s*([^:\n]*?(?:2025|25))'
            ],
            'Total Bill Amount': [
                r'Total\s+Bill\s+Amount\s*:?\s*(\d+)',
                r'Estimated\s+(?:Bill\s+)?Amount\s*:?\s*(\d+)',
                r'Bill\s+Amount\s*:?\s*(\d+)'
            ],
            'UHID Number': [
                r'UHID\s+Number\s*:?\s*([A-Z0-9]+)',
                r'UHID\s*:?\s*([A-Z0-9]+)',
                r'Hospital\s+ID\s*:?\s*([A-Z0-9]+)'
            ],
            'Remarks': [
                r'Remarks\s*:?\s*\n([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless))',
                r'Remarks\s*:?\s*([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless))',
                r'Pre\s*authorization\s+request\s+is\s+approved[^.]*\.[^.]*\.[^.]*\.',
                r'Remarks\s*:?\s*([^:]+?)(?:\n(?:[A-Z][a-z]+\s+related|Network|Hospital|Amount|Event|Final))'
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
                    page_text = pytesseract.image_to_string(img, config='--psm 6')

                text += page_text + "\n"

            doc.close()
            return text

        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""

    def clean_extracted_value(self, value, field_name):
        if not value:
            return None

        value = value.strip()

        if field_name == 'Name of the Patient':
            value = ' '.join(value.split())
            if 'is discharged' in value.lower() or len(value.split()) < 2:
                return None
            return value

        elif field_name in ['Date of Admission', 'Date of Discharge']:
            value = re.sub(r'\s+', '-', value)
            if not re.search(r'\d', value):
                return None
            return value

        elif field_name in ['Approved Amount', 'Total Bill Amount']:
            numbers = re.findall(r'\d+', value)
            return numbers[0] if numbers else None

        elif field_name == 'Policy Period':
            value = re.sub(r'\s+', ' ', value)
            return value

        elif field_name == 'Remarks':
            value = re.sub(r'\s+', ' ', value)
            value = re.sub(r'^(Remarks?\s*:?\s*)', '', value, flags=re.IGNORECASE)
            return value.strip()

        elif field_name == 'AL Number':
            value = re.sub(r'[^A-Z0-9\-/]', '', value)
            return value if len(value) > 3 else None

        return value

    def extract_field(self, text, field_name):
        patterns = self.patterns.get(field_name, [])

        if field_name == 'Remarks':
            return self.extract_remarks(text)

        if field_name in ['Date of Admission', 'Date of Discharge']:
            policy_match = re.search(r'Policy\s+Period\s*:?.*?\n', text, re.IGNORECASE)
            if policy_match:
                text = text[policy_match.end():]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if matches:
                value = self.clean_extracted_value(matches[0], field_name)
                if value:
                    return value

        return None

    def extract_remarks(self, text):
        pattern1 = r'Remarks\s*:?.*?\n?(Pre\s*authorization\s+request\s+is\s+approved.*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless|Terms\s+and\s+Conditions))'
        match = re.search(pattern1, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            remarks = match.group(1).strip()
            remarks = re.sub(r'\s+', ' ', remarks)
            return remarks

        pattern2 = r'Remarks\s*:?.*?([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless|Terms\s+and\s+Conditions))'
        match = re.search(pattern2, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            remarks = match.group(1).strip()
            remarks = re.sub(r'\s+', ' ', remarks)
            if len(remarks) > 50:
                return remarks

        return None

    def extract_all_data(self, pdf_path):
        text = self.extract_text_from_pdf(pdf_path)

        if not text.strip():
            print("No text could be extracted from the PDF")
            return None

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
                formatted_data = {
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
