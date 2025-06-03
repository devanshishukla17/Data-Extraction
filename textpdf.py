import re
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io

class PDFDataExtractor:
    def __init__(self):
        self.patterns = {
            'AL Number': [
                r'AL Number\s*:?\s*([A-Z0-9\-/]+)',
                r'Authorization\s+(?:Letter\s+)?Number\s*:?\s*([A-Z0-9\-/]+)',
                r'AL\s+No\s*:?\s*([A-Z0-9\-/]+)'
            ],
            'Approved Amount': [
                r'Final\s+(?:Sanctioned|Approved)\s+Amount\s*:?\s*(\d+)',
                r'Amount\s+(?:to\s+be\s+)?(?:sanctioned|approved)\s*:?\s*[Rs\.\s]*(\d+)',
                r'guarantee\s+for\s+payment\s+of\s+Rs\s*(\d+)',
                r'Sanctioned\s+Amount\s*:?\s*(\d+)'
            ],
            'Date of Admission': [
                r'Date\s+of\s+Admission\s*:?\s*([^\n:]+)'
            ],
            'Date of Discharge': [
                r'Date\s+of\s+Discharge\s*:?\s*([^\n:]+)'
            ],
            'Name of the Patient': [
                r'Name\s+of\s+(?:the\s+)?Patient\s*:?\s*([A-Z\s\.]+?)(?:\n|UHID|Age|Gender)',
                r'Patient\s+Name\s*:?\s*([A-Z\s\.]+?)(?:\n|UHID|Age|Gender)',
                r'Patient\s*:?\s*([A-Z\s\.]+?)(?:\n|UHID|Age|Gender)'
            ],
            'Policy No': [
                r'Policy\s+No\s*:?\s*([A-Z0-9\/\-]+)',
                r'Policy\s+Number\s*:?\s*([A-Z0-9\/\-]+)'
            ],
            'Policy Period': [
                r'Policy\s+Period\s*:?\s*([^:\n]+?)(?:\n|Date\s+of)',
                r'Policy\s+Term\s*:?\s*([^:\n]+?)(?:\n|Date\s+of)'
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
                # This pattern will capture the longer remarks section
                r'Remarks\s*:?\s*\n([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless))',
                r'Remarks\s*:?\s*([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless))',
                # Fallback patterns
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
                
                # If no text found, use OCR
                if not page_text.strip():
                    print(f"No text found on page {page_num + 1}, using OCR...")
                    # Convert page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Use OCR
                    page_text = pytesseract.image_to_string(img, config='--psm 6')
                
                text += page_text + "\n"
            
            doc.close()
            return text
            
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""
    
    def clean_extracted_value(self, value, field_name):
        """Clean and format extracted values"""
        if not value:
            return None
        
        value = value.strip()

        if field_name == 'Name of the Patient':
            # Remove extra spaces and ensure proper case
            value = ' '.join(value.split())
            return value if len(value) > 2 else None
        
        elif field_name in ['Date of Admission', 'Date of Discharge']:
            # Standardize date format
            value = re.sub(r'\s+', '-', value)
            return value
        
        elif field_name in ['Approved Amount', 'Total Bill Amount']:
            # Extract only numbers
            numbers = re.findall(r'\d+', value)
            return numbers[0] if numbers else None
        
        elif field_name == 'Policy Period':
            # Clean policy period
            value = re.sub(r'\s+', ' ', value)
            return value
        
        elif field_name == 'Remarks':
            # Clean remarks
            value = re.sub(r'\s+', ' ', value)
            # Remove common prefixes
            value = re.sub(r'^(Remarks?\s*:?\s*)', '', value, flags=re.IGNORECASE)
            return value.strip()
        
        return value
    
    
    def extract_field(self, text, field_name):
        """Extract a specific field from text using multiple patterns"""
        patterns = self.patterns.get(field_name, [])

        # Special handling for Remarks field
        if field_name == 'Remarks':
            return self.extract_remarks(text)

        # For Date of Admission and Discharge, search only after 'Policy Period'
        if field_name in ['Date of Admission', 'Date of Discharge']:
            policy_match = re.search(r'Policy\s+Period\s*:?.*?\n', text, re.IGNORECASE)
            if policy_match:
                text = text[policy_match.end():]

        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if matches:
                #print(f"DEBUG: Pattern {i+1} matched for {field_name}: {matches[0]}")
                value = self.clean_extracted_value(matches[0], field_name)
                if value:
                    return value

        return None
    def extract_remarks(self, text):
        # Look for the specific remarks pattern that starts with "Pre authorization request"
        pattern1 = r'Remarks\s*:?\s*\n?(Pre\s*authorization\s+request\s+is\s+approved.*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless|Terms\s+and\s+Conditions))'
        
        match = re.search(pattern1, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            remarks = match.group(1).strip()
            # Clean up the text
            remarks = re.sub(r'\s+', ' ', remarks)
            return remarks
        
        # Fallback: Look for any text after "Remarks:" until certain keywords
        pattern2 = r'Remarks\s*:?\s*([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless|Terms\s+and\s+Conditions))'
        
        match = re.search(pattern2, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            remarks = match.group(1).strip()
            # Clean up the text
            remarks = re.sub(r'\s+', ' ', remarks)
            # Remove the short remarks if it's just deduction info
            if len(remarks) > 50:  # Only return if it's substantial
                return remarks
        
        return None
    
    def extract_all_data(self, pdf_path):
        """Extract all required fields from PDF"""
        print(f"Processing PDF: {pdf_path}")
        
        # Extract text from PDF
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text.strip():
            print("No text could be extracted from the PDF")
            return None
        
        # Extract each field
        extracted_data = {}
        
        for field_name in self.patterns.keys():
            extracted_data[field_name] = self.extract_field(text, field_name)
        
        # Add Letter Type (assuming it's always Authorization Letter based on the sample)
        extracted_data['Letter Type'] = 'Authorization Letter'
        
        return extracted_data
    
    def process_pdf(self, pdf_path):
        """Main method to process PDF and return JSON output"""
        try:
            if not Path(pdf_path).exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            data = self.extract_all_data(pdf_path)
            
            if data:
                # Format output to match the required structure
                formatted_data = {
                    #"AL Number": data.get('AL Number'),
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
    """Main function to run the PDF extractor"""
    # Option 1: Use command line argument
    if len(sys.argv) == 2:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "pdf1.pdf"  # Change this to your PDF filename
        print(f"No command line argument provided, using default: {pdf_path}")
    
    # Initialize extractor
    extractor = PDFDataExtractor()
    
    # Process PDF
    result = extractor.process_pdf(pdf_path)
    
    if result:
        # Output as JSON
        print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print("Failed to extract data from PDF")
        sys.exit(1)

if __name__ == "__main__":
    main()