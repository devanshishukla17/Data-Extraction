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
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            for page in doc:
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
            print(f"Error extracting text from PDF: {e}", file=sys.stderr)
            return ""

    def extract_address_layout(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
            page = doc[0]  
            words = page.get_text("words")
            
            address_lines = []
            start_y = None
            end_y = None
            stop_processing = False

            # Find "To,"
            for w in words:
                if w[4].strip() == 'To,': 
                    start_y = w[3]  
                    break
            if start_y is None:
                return "null"

            for w in words:
                if w[4].strip().startswith('Subject') and w[3] > start_y:
                    end_y = w[1]  
                    break
            if end_y is None:
                end_y = start_y + 150

            lines = {}
            for w in words:
                if 'Inlias' in w[4] or ('ID' in w[4] and ':' in w[4]):
                    stop_processing = True
                    continue
                    
                if stop_processing:
                    continue
                    
                if start_y < w[1] < end_y and w[0] < 250:  
                    y = round(w[1], 1)
                    lines.setdefault(y, []).append(w[4])

            sorted_lines = [lines[y] for y in sorted(lines)]
            full_lines = [' '.join(line) for line in sorted_lines]
            
            address = ', '.join(full_lines)
            address = address.rstrip(', ')
            return address if address else "null"
            
        except Exception as e:
            print(f"Error extracting address layout: {e}", file=sys.stderr)
            return "null"
        finally:
            if 'doc' in locals():
                doc.close()

    def extract_al_number(self, text):
        try:
            match = re.search(r'AL\s*No\s*:\s*([^\s]+)', text)
            return match.group(1) if match else None
        except Exception as e:
            print(f"Error extracting AL Number: {e}", file=sys.stderr)
            return None

    def extract_patient_name(self, text):
        try:
            match = re.search(r'Subject\s*:-\s*Denial\s*of\s*Pre-Auth\s*for\s*([^\n]+)', text)
            return match.group(1).strip() if match else None
        except Exception as e:
            print(f"Error extracting patient name: {e}", file=sys.stderr)
            return None

    def extract_table_values(self, text):
        try:
            clean_text = ' '.join(text.split())
            direct_match = re.search(
                r'Member ID[:\s]+(\d+).*?Policy Number[:\s]+(\d+)',
                clean_text,
                re.IGNORECASE
            )
            if direct_match:
                return direct_match.group(1), direct_match.group(2)
            table_match = re.search(
                r'Member ID\s*\|\s*(\d+).*?Policy Number\s*\|\s*(\d+)',
                clean_text,
                re.IGNORECASE
            )
            if table_match:
                return table_match.group(1), table_match.group(2)
        
            lines = text.split('\n')
            member_id = None
            policy_number = None
        
            for line in lines:
                if not member_id and ('Member ID' in line or 'UHID' in line):
                    member_match = re.search(r'[:\|]\s*(\d+)', line)
                    if member_match:
                        member_id = member_match.group(1)

                if not policy_number and ('Policy Number' in line or 'Policy No' in line):
                    policy_match = re.search(r'[:\|]\s*(\d+)', line)
                    if policy_match:
                        policy_number = policy_match.group(1)
        
            return member_id, policy_number
        
        except Exception as e:
            print(f"Error extracting table values: {e}", file=sys.stderr)
            return None, None
        
    def extract_reason(self, text):
        try:
            # Find the section between the two markers
            reason_match = re.search(
                r'conditions of the policy stated below:(.*?)Your request for a cashless facility',
                text,
                re.DOTALL | re.IGNORECASE
            )
        
            if not reason_match:
                return None
            
            reason_text = reason_match.group(1).strip()
        
            # Clean up the text - remove extra whitespace and newlines
            reason_text = ' '.join(reason_text.split())
        
            # Remove any leading/trailing punctuation
            reason_text = reason_text.strip('.,;:- ')
        
            return reason_text if reason_text else None
        
        except Exception as e:
            print(f"Error extracting reason: {e}", file=sys.stderr)
            return None

    def extract_non_registration_patient_name(self, text):
        try:
            match = re.search(
                r'We have received the documents \(AL No :-.*?\) In the name of (.*?) filed by you',
                text,
                re.DOTALL
            )
            if match:
                name = match.group(1).strip()
                # Clean up the name by removing any extra whitespace or line breaks
                name = ' '.join(name.split())
                return name
            return None
        except Exception as e:
            print(f"Error extracting non-registration patient name: {e}", file=sys.stderr)
            return None

    def extract_non_registration_reason(self, text):
        try:
            match = re.search(
                r'Details of the reasons are given below\.(.*?)In case you require any additional assistance',
                text,
                re.DOTALL
            )
            if match:
                reason = match.group(1).strip()
                # Clean up the reason text
                reason = '\n'.join(line.strip() for line in reason.split('\n') if line.strip())
                return reason
            return None
        except Exception as e:
            print(f"Error extracting non-registration reason: {e}", file=sys.stderr)
            return None

    def extract_non_registration_address(self, text):
        try:
            lines = text.split('\n')
            date_line_index = -1
            subject_line_index = -1
            
            for i, line in enumerate(lines):
                if line.strip().startswith('Date') and date_line_index == -1:
                    date_line_index = i
                if line.strip().startswith('Subject') and subject_line_index == -1:
                    subject_line_index = i
                    break
            
            if date_line_index != -1 and subject_line_index != -1 and date_line_index < subject_line_index:
                address_lines = []
                for line in lines[date_line_index+1:subject_line_index]:
                    stripped_line = line.strip()
                    if stripped_line:
                        address_lines.append(stripped_line)
                return '\n'.join(address_lines)
            return None
        except Exception as e:
            print(f"Error extracting non-registration address: {e}", file=sys.stderr)
            return None

    def process_denial_letter(self, pdf_path):
        text = self.extract_text_from_pdf(pdf_path)
        if not text.strip():
            return None

        # Get the first line to determine the type of document
        first_line = text.split('\n')[0].strip()

        if first_line.lower().startswith("denial letter"):
            # Process as Denial Letter
            hospital_address = self.extract_address_layout(pdf_path)
            al_number = self.extract_al_number(text)
            patient_name = self.extract_patient_name(text)
            member_id, policy_number = self.extract_table_values(text)
            reason = self.extract_reason(text) 

            return {
                "AL Number": al_number,
                "UHID Number": member_id,
                "Name of the Patient": patient_name,
                "Policy Number": policy_number,
                "Hospital Address": hospital_address,
                "Reason": reason
            }
        elif "NON - REGISTRATION OF CLAIM" in first_line:
            # Process as Non-Registration of Claim
            patient_name = self.extract_non_registration_patient_name(text)
            reason = self.extract_non_registration_reason(text)
            hospital_address = self.extract_non_registration_address(text)

            return {
                "Name of the Patient": patient_name,
                "Hospital Address": hospital_address,
                "Reason": reason
            }
        else:
            return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python denial_extractor.py <path_to_pdf>", file=sys.stderr)
        sys.exit(1)

    extractor = DenialLetterExtractor()
    result = extractor.process_denial_letter(sys.argv[1])

    if result:
        print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print("null")
    
if __name__ == "__main__":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    main()