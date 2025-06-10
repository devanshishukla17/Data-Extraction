# import re
# import json
# import sys
# from pathlib import Path
# import fitz  # PyMuPDF
# from PIL import Image
# import pytesseract
# import io
# import numpy as np
# import cv2

# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# class DataExtractor:
#     def __init__(self):
#         self.patterns = {
#             'AL Number': [
#                 r'AL(?:\s*Number)?\s*:?\s*([A-Z0-9\-/]{5,})',
#                 r'Authorization\s+Letter\s+Number\s*:?\s*([A-Z0-9\-/]{5,})'
#             ],
#             'Approved Amount': [
#                 r'Final\s+(?:Sanctioned|Approved)\s+Amount\s*:?\s*(\d+)',
#                 r'Amount\s+(?:to\s+be\s+)?(?:sanctioned|approved)\s*:?\s*[Rs\.\s]*(\d+)',
#                 r'guarantee\s+for\s+payment\s+of\s+Rs\s*(\d+)',
#                 r'Sanctioned\s+Amount\s*:?\s*(\d+)'
#             ],
#             'Date of Admission': [
#                 r'Date\s+of\s+Admission\s*:?\s*([^\n:]*?(?:2025|25))'
#             ],
#             'Date of Discharge': [
#                 r'Date\s+of\s+Discharge\s*:?\s*([^\n:]*?(?:2025|25))',
#                 r'Discharge\s+Date\s*:?\s*([^\n:]*?(?:2025|25))'
#             ],
#             'Name of the Patient': [
#                 r'(?:Name\s+of\s+(?:the\s+)?Patient|Patient\s+Name)\s*:?\s*([^\n]+)'
#             ],
#             'Policy No': [
#                 r'Policy\s+No\s*:?\s*([A-Z0-9\/\-]+)',
#                 r'Policy\s+Number\s*:?\s*([A-Z0-9\/\-]+)'
#             ],
#             'Policy Period': [
#                 r'Policy\s+Period\s*:?\s*(.*?)(?=Non-Medical)'
#             ],
#             'Total Bill Amount': [
#                 r'Total\s+Bill\s+Amount\s*:?\s*(\d+)',
#                 r'Estimated\s+(?:Bill\s+)?Amount\s*:?\s*(\d+)',
#                 r'Bill\s+Amount\s*:?\s*(\d+)'
#             ],
#             'UHID Number': [
#                 r'UHID\s*Number\s*:?\s*([A-Z0-9]{8,20})',
#                 r'UHID\s*:?\s*([A-Z0-9]{8,20})'
#             ],
#             'Remarks': [
#                 r'Remarks\s*:?\s*\n([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless))',
#                 r'Remarks\s*:?\s*([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless))',
#                 r'Pre\s*authorization\s+request\s+is\s+approved[^.]*\.[^.]*\.[^.]*\.',
#                 r'Remarks\s*:?\s*([^:]+?)(?:\n(?:[A-Z][a-z]+\s+related|Network|Hospital|Amount|Event|Final))'
#             ]
#         }

#     def preprocess_image(self, image):
#         try:
#             open_cv_image = np.array(image)
#             if len(open_cv_image.shape) == 3:
#                 open_cv_image = open_cv_image[:, :, ::-1].copy()
#             if len(open_cv_image.shape) == 3:
#                 gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
#             else:
#                 gray = open_cv_image
#             thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
#                                            cv2.THRESH_BINARY, 11, 2)
#             kernel = np.ones((1, 1), np.uint8)
#             opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
#             return Image.fromarray(opening)
#         except Exception as e:
#             print(f"Warning: Image preprocessing failed: {e}. Using original image.")
#             return image

#     def extract_text_from_pdf(self, pdf_path):
#         try:
#             doc = fitz.open(pdf_path)
#             text = ""
#             for page_num in range(len(doc)):
#                 page = doc.load_page(page_num)
#                 page_text = page.get_text()

#                 if not page_text.strip():
#                     pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
#                     img_data = pix.tobytes("png")
#                     img = Image.open(io.BytesIO(img_data))
#                     img = self.preprocess_image(img)
#                     page_text = pytesseract.image_to_string(img, config='--psm 6')

#                 text += page_text + "\n"

#             doc.close()
#             return text

#         except Exception as e:
#             print(f"Error extracting text from PDF: {e}")
#             return ""

#     def clean_extracted_value(self, value, field_name):
#         if not value:
#             return None

#         value = value.strip()

#         if field_name == 'Name of the Patient':
#             for stop_word in ["Policy", "UHID", "Co-Pay", ":", "  "]:
#                 if stop_word in value:
#                     value = value.split(stop_word)[0]
#             value = ' '.join(value.split())
#             return value if len(value.split()) >= 2 else None

#         elif field_name in ['Date of Admission', 'Date of Discharge']:
#             value = re.sub(r'\s+', '-', value.upper())
#             if not re.search(r'\d', value):
#                 return None
#             return value

#         elif field_name in ['Approved Amount', 'Total Bill Amount']:
#             numbers = re.findall(r'\d+', value)
#             return numbers[0] if numbers else None

#         elif field_name == 'Policy Period':
#             return value.strip()

#         elif field_name == 'Remarks':
#             value = re.sub(r'\s+', ' ', value)
#             value = re.sub(r'^(Remarks?\s*:?\s*)', '', value, flags=re.IGNORECASE)
#             return value.strip()

#         elif field_name == 'AL Number':
#             value = re.sub(r'[^A-Z0-9\-/]', '', value)
#             return value if len(value) > 3 else None

#         elif field_name == 'UHID Number':
#             value = value.strip().upper().replace('1L', 'IL')
#             return value

#         return value

#     def extract_field(self, text, field_name):
#         patterns = self.patterns.get(field_name, [])

#         if field_name == 'Remarks':
#             return self.extract_remarks(text)

#         if field_name == 'Policy Period':
#             policy_block = re.search(r'Policy\s+Period.*?Non-Medical', text, re.IGNORECASE | re.DOTALL)
#             if policy_block:
#                 for pattern in patterns:
#                     match = re.search(pattern, policy_block.group(), re.IGNORECASE)
#                     if match:
#                         return self.clean_extracted_value(match.group(1), field_name)

#         for pattern in patterns:
#             matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
#             if matches:
#                 value = self.clean_extracted_value(matches[0], field_name)
#                 if value:
#                     return value

#         return None

#     def extract_remarks(self, text):
#         pattern1 = r'Remarks\s*:?.*?\n?(Pre\s*authorization\s+request\s+is\s+approved.*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless|Terms\s+and\s+Conditions))'
#         match = re.search(pattern1, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
#         if match:
#             remarks = match.group(1).strip()
#             remarks = re.sub(r'\s+', ' ', remarks)
#             return remarks

#         pattern2 = r'Remarks\s*:?.*?([^:]*?)(?=(?:Important\s+Note|For\s+Real\s+time|Address|For\s+any\s+cashless|Terms\s+and\s+Conditions))'
#         match = re.search(pattern2, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
#         if match:
#             remarks = match.group(1).strip()
#             remarks = re.sub(r'\s+', ' ', remarks)
#             if len(remarks) > 50:
#                 return remarks

#         return None

#     def extract_all_data(self, pdf_path):
#         text = self.extract_text_from_pdf(pdf_path)

#         if not text.strip():
#             print("No text could be extracted from the PDF")
#             return None

#         extracted_data = {}
#         for field_name in self.patterns.keys():
#             extracted_data[field_name] = self.extract_field(text, field_name)

#         extracted_data['Letter Type'] = 'Authorization Letter'
#         return extracted_data

#     def process_pdf(self, pdf_path):
#         try:
#             if not Path(pdf_path).exists():
#                 raise FileNotFoundError(f"PDF file not found: {pdf_path}")

#             data = self.extract_all_data(pdf_path)

#             if data:
#                 formatted_data = {
#                     "AL Number": data.get('AL Number'),
#                     "Approved Amount": data.get('Approved Amount'),
#                     "Date of Admission": data.get('Date of Admission'),
#                     "Date of Discharge": data.get('Date of Discharge'),
#                     "Letter Type": data.get('Letter Type'),
#                     "Name of the Patient": data.get('Name of the Patient'),
#                     "Policy No": data.get('Policy No'),
#                     "Policy Period": data.get('Policy Period'),
#                     "Remarks": data.get('Remarks'),
#                     "Total Bill Amount": data.get('Total Bill Amount'),
#                     "UHID Number": data.get('UHID Number')
#                 }

#                 return formatted_data
#             else:
#                 return None

#         except Exception as e:
#             print(f"Error processing PDF: {e}")
#             return None

# def main():
#     if len(sys.argv) == 2:
#         pdf_path = sys.argv[1]
#     else:
#         pdf_path = "img_pdf2.pdf"
#         print(f"No command line argument provided, using default: {pdf_path}")

#     extractor = DataExtractor()
#     result = extractor.process_pdf(pdf_path)

#     if result:
#         print(json.dumps(result, indent=4, ensure_ascii=False))
#     else:
#         print("Failed to extract data from PDF")
#         sys.exit(1)

# if __name__ == "__main__":
#     main()

#-----------------------------------------------------------------------------------------------------------------

import re
import cv2
import numpy as np
from datetime import datetime
from PIL import Image

def normalize_text(s):
    """Normalize text by replacing special characters and whitespace."""
    if s is None:
        return None
    return s.replace('\u00A0', ' ').replace('­', '-').replace('–', '-').replace('—', '-').strip()

def clean_patient_name(name_text):
    """Clean patient name by removing trailing text like 'Policy related Deductions'."""
    if not name_text:
        return None
        
    # Split by common separators that might appear in the line
    for separator in ["Policy", "Co-Pay", "UHID", ":", "  "]:
        if separator in name_text:
            name_text = name_text.split(separator)[0].strip()
    
    # Remove any trailing whitespace or punctuation
    name_text = name_text.strip()
    
    return name_text

def extract_policy_period(text, debug=False):
    """Extract policy period from text with improved handling for multi-line periods."""
    lines = text.split("\n")
    policy_period_value = None
    
    # First pass: Look for complete policy period on a single line
    for i, line in enumerate(lines):
        normalized_line = normalize_text(line)
        # Look for the line containing "Policy Period"
        if re.search(r"Policy\s+Period", normalized_line, re.IGNORECASE):
            if debug: print(f"DEBUG: Found potential Policy Period line {i}: ", repr(normalized_line))
            
            # Extract the value part after "Policy Period" (and optional colon)
            match = re.search(r"Policy\s+Period\s*:?\s*(.*)", normalized_line, re.IGNORECASE)
            if match:
                current_value = match.group(1).strip()
                if debug: print(f"DEBUG: Initial value from line {i}: ", repr(current_value))
                
                # If the value is empty or just contains a colon, check the next line
                if not current_value or current_value == ":":
                    if debug: print(f"DEBUG: Empty value on line {i}, checking next line")
                    
                    # Look at the next non-empty line
                    next_line_index = i + 1
                    while next_line_index < len(lines) and not lines[next_line_index].strip():
                        next_line_index += 1
                    
                    if next_line_index < len(lines):
                        next_line = normalize_text(lines[next_line_index])
                        if debug: print(f"DEBUG: Next non-empty line {next_line_index}: ", repr(next_line))
                        
                        # Check if the next line contains a date range
                        date_range_match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4}\s+to\s+\d{1,2}-[A-Za-z]{3}-\d{4})", next_line, re.IGNORECASE)
                        if date_range_match:
                            policy_period_value = date_range_match.group(1)
                            if debug: print(f"DEBUG: Found complete date range on next line: ", repr(policy_period_value))
                            break
                        
                        # Check if the next line contains a partial date range
                        partial_match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4}\s+to\s+\d{1,2}-[A-Za-z]{3}-)", next_line, re.IGNORECASE)
                        if partial_match:
                            partial_value = partial_match.group(1)
                            if debug: print(f"DEBUG: Found partial date range on next line: ", repr(partial_value))
                            
                            # Look for the year on the line after that
                            year_line_index = next_line_index + 1
                            while year_line_index < len(lines) and not lines[year_line_index].strip():
                                year_line_index += 1
                            
                            if year_line_index < len(lines):
                                year_line = normalize_text(lines[year_line_index])
                                if debug: print(f"DEBUG: Checking line {year_line_index} for year: ", repr(year_line))
                                
                                # Check if the line starts with a 4-digit year
                                year_match = re.match(r"^(\d{4})", year_line)
                                if year_match:
                                    year = year_match.group(1)
                                    policy_period_value = partial_value + year 
                                    if debug: print(f"DEBUG: Combined with year from line {year_line_index}: ", repr(policy_period_value))
                                    break
                        
                        # If no date pattern found, use the entire next line as a fallback
                        if not policy_period_value and re.search(r"\d", next_line):  # Only if it contains at least one digit
                            policy_period_value = next_line
                            if debug: print(f"DEBUG: Using entire next line as fallback: ", repr(policy_period_value))
                            break
                
                # Check if the value looks like a complete date range
                complete_match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4}\s+to\s+\d{1,2}-[A-Za-z]{3}-\d{4})", current_value, re.IGNORECASE)
                if complete_match:
                    policy_period_value = complete_match.group(1)
                    if debug: print(f"DEBUG: Complete value found on line {i}: ", repr(policy_period_value))
                    break  # Found complete value, stop searching
                
                # Check if the value looks like 'DD-MMM-YYYY to DD-MMM-' (incomplete)
                incomplete_match = re.match(r"(\d{1,2}-[A-Za-z]{3}-\d{4}\s+to\s+\d{1,2}-[A-Za-z]{3}-)$", current_value, re.IGNORECASE)
                
                if incomplete_match or current_value.endswith("-"):
                    if debug: print(f"DEBUG: Value on line {i} appears incomplete: ", repr(current_value))
                    
                    # Look ahead for the year on subsequent lines
                    for j in range(i+1, min(i+5, len(lines))):  # Check up to 5 lines ahead
                        next_line = normalize_text(lines[j])
                        if debug: print(f"DEBUG: Checking line {j} for year: ", repr(next_line))
                        
                        # Check if the next line starts with a 4-digit year
                        year_match = re.match(r"^(\d{4})", next_line)
                        if year_match:
                            year = year_match.group(1)
                            if debug: print(f"DEBUG: Found year on line {j}: ", repr(year))
                            
                            # Combine: ensure trailing hyphen exists before appending year
                            base_value = current_value.strip()
                            if not base_value.endswith("-"):
                                base_value += "-"
                            policy_period_value = base_value + year
                            if debug: print(f"DEBUG: Combined value with year: ", repr(policy_period_value))
                            break  # Found year, stop searching ahead
                        
                        # Also check if the line contains the full date (sometimes the entire "to DATE" part is on next line)
                        date_match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4})", next_line)
                        if date_match and "to" not in current_value:
                            end_date = date_match.group(1)
                            if debug: print(f"DEBUG: Found end date on line {j}: ", repr(end_date))
                            
                            # Check if current_value already has a date
                            if re.search(r"\d{1,2}-[A-Za-z]{3}-\d{4}", current_value):
                                policy_period_value = f"{current_value.strip()} to {end_date}"
                                if debug: print(f"DEBUG: Combined with end date: ", repr(policy_period_value))
                                break
                    
                    # If we found a combined value, stop the outer loop too
                    if policy_period_value:
                        break
                else:
                    # If it doesn't match the specific incomplete pattern, store it as a fallback
                    # Only store if it contains digits to avoid storing labels like "Policy Period:"
                    if re.search(r"\d", current_value):
                        policy_period_value = current_value
                        if debug: print(f"DEBUG: Using value as fallback: ", repr(policy_period_value))
                    # Don't break here, continue searching in case a better match exists
    
    # Second pass: If we didn't find a policy period with the label, look for date patterns
    if not policy_period_value:
        for i, line in enumerate(lines):
            normalized_line = normalize_text(line)
            # Look for a pattern like "DD-MMM-YYYY to DD-MMM-YYYY"
            date_range_match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4}\s+to\s+\d{1,2}-[A-Za-z]{3}-\d{4})", normalized_line, re.IGNORECASE)
            if date_range_match:
                policy_period_value = date_range_match.group(1)
                if debug: print(f"DEBUG: Found date range without label on line {i}: ", repr(policy_period_value))
                break
    
    # Final cleanup
    if policy_period_value:
        # Ensure spacing around 'to'
        policy_period_value = re.sub(r"\s*to\s*", " to ", policy_period_value).strip()
        # Remove trailing hyphens if any resulted from normalization or incomplete extraction
        policy_period_value = re.sub(r"-\s*$", "", policy_period_value).strip()
        # Ensure the final format is DD-MMM-YYYY to DD-MMM-YYYY
        final_match = re.match(r"(\d{1,2}-[A-Za-z]{3}-\d{4})\s+to\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", policy_period_value, re.IGNORECASE)
        if final_match:
            policy_period_value = f"{final_match.group(1)} to {final_match.group(2)}"
        else:
             # If it doesn't match the final format, maybe it's invalid, return None or log warning
             if debug: print(f"DEBUG: Final value ", repr(policy_period_value), " does not match expected format.")
             # For now, return the cleaned value, but might need stricter validation
             pass 

        if debug: print(f"DEBUG: Final cleaned Policy Period: ", repr(policy_period_value))
        
    return policy_period_value

def extract_authorization_letter_fields(text, with_ocr=False):
    """Extract fields specific to Authorization Letter."""
    # Extract AL Number
    al_number = None
    al_patterns = [
        r"AL\s*Number\s*:\s*([^\s\n]+)",
        r"AL\s*Number\s*[:#]\s*([0-9-]+)",
        r"AL\s*No\.?\s*[:#]?\s*([0-9-]+)",
        r"AL\s*Number[:#]?\s*([0-9-]+)",
        r"AL\s*Number[:#]?\s*([^\n\r]+)"
    ]
    for pattern in al_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            al_number = match.group(1).strip()
            break

    # Extract patient name
    patient_name = None
    if with_ocr:
        name_patterns = [
            r"Name\s+of\s+the\s+Patient\s*:\s*([^:\n]+?)(?=\s{2,}|\t|Policy|UHID|Co-Pay|$)",
            r"Patient\s+Name\s*:\s*([^:\n]+?)(?=\s{2,}|\t|Policy|UHID|Co-Pay|$)",
            r"Name\s+of\s+the\s+Patient\s+([A-Z][A-Z\s]+)(?=\s{2,}|\t|Policy|UHID|Co-Pay|$)",
            r"Name\s+of\s+the\s+Patient\s*:\s*([^\n]+)",
            r"Patient\s+Name\s*:\s*([^\n]+)"
        ]
    else:
        name_patterns = [
            r"Name\s+of\s+the\s+Patient\s*:\s*([^:\n]+)",
            r"Patient\s+Name\s*:\s*([^:\n]+)",
            r"Patient\s*:\s*([^:\n]+)",
            r"Name\s+of\s+Patient\s*:\s*([^:\n]+)"
        ]
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_name = match.group(1).strip()
            patient_name = clean_patient_name(raw_name)
            break

    # Extract UHID Number
    uhid_number = None
    uhid_patterns = [
        r"UHID\s*Number\s*:\s*([^\s\n:]+)",
        r"UHID\s*No\.?\s*:\s*([^\s\n:]+)",
        r"UHID\s*:\s*([^\s\n:]+)",
        r"UHID\s*Number\s*[:#]\s*([^\n\r:]+)"
    ]
    for pattern in uhid_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            uhid_number = match.group(1).strip()
            break

    # Extract Policy Number
    policy_no = None
    policy_patterns = [
        r"Policy\s*No\s*:\s*([^\s\n:]+)",
        r"Policy\s*Number\s*:\s*([^\s\n:]+)",
        r"Policy\s*:\s*([^\s\n:]+)",
        r"Policy\s*No\.?\s*[:#]\s*([^\n\r:]+)",
        r"Policy\s*No\s+([0-9/X]+)"
    ]
    for pattern in policy_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            policy_no = match.group(1).strip()
            break

    # Extract Total Bill Amount
    total_amount = None
    total_patterns = [
        r"Total\s+Bill\s+Amount\s*:\s*([\d,]+)",
        r"Total\s+Bill\s*:\s*([\d,]+)",
        r"Total\s+Amount\s*:\s*([\d,]+)",
        r"Bill\s+Amount\s*:\s*([\d,]+)",
        r"Total\s+Bill\s+Amount\s+([\d,]+)"
    ]
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            total_amount = match.group(1).strip()
            break
    if not total_amount:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if re.search(r"Total\s+Bill\s+Amount", line, re.IGNORECASE):
                for j in range(i, min(i+3, len(lines))):
                    amount_match = re.search(r"[\d,]+", lines[j])
                    if amount_match:
                        total_amount = amount_match.group(0).strip()
                        break
                if total_amount:
                    break

    # Extract Approved Amount
    approved_amount = None
    approved_patterns = [
        r"guarantee\s+for\s+payment\s+of\s+Rs\s*([\d,]+)",
        r"payment\s+of\s+Rs\s*([\d,]+)",
        r"Approved\s+Amount\s*:\s*([\d,]+)",
        r"Final\s+Approved\s+Amount\s*[:#]?\s*([\d,]+)",
        r"Rs\s*([\d,]+)\s+\(in words\)"
    ]
    for pattern in approved_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            approved_amount = match.group(1).strip()
            break

    def format_date(date_str):
        """Format date string to standard format."""
        if not date_str:
            return None
        date_str = normalize_text(date_str).replace(" ", "-")
        formats = [
            "%d-%b-%Y", "%d-%b-%y", "%d%b%Y", "%d%b%y",
            "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"
        ]
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                if date_obj.year < 100:
                     date_obj = date_obj.replace(year=date_obj.year + (1900 if date_obj.year > 50 else 2000))
                return date_obj.strftime("%d-%b-%Y")
            except ValueError:
                continue
        if len(date_str) == 8 and date_str.isdigit():
            try:
                date_obj = datetime.strptime(date_str, "%d%m%Y")
                return date_obj.strftime("%d-%b-%Y")
            except ValueError:
                pass
        return date_str

    def extract_date(label_patterns):
        """Extract date using multiple patterns."""
        for label in label_patterns:
            pattern = fr"{label}\s*:\s*(\d{{1,2}}[-\s]?[A-Za-z]{{3}}[-\s]?\d{{2,4}})"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return format_date(match.group(1))
            pattern = fr"{label}\s*:\s*(\d{{1,2}}[-/\s]\d{{1,2}}[-/\s]\d{{2,4}})"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return format_date(match.group(1))
            pattern = fr"{label}\s+(\d{{1,2}}[-\s]?[A-Za-z]{{3}}[-\s]?\d{{2,4}})"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return format_date(match.group(1))
        return None

    def clean_number(num_str):
        """Clean numeric values by removing commas."""
        if not num_str:
            return None
        return num_str.replace(",", "").strip()

    # Extract dates
    admission_date = extract_date([
        "Date of Admission", 
        "Admission Date", 
        "DOA"
    ])
    discharge_date = extract_date([
        "Date of Discharge", 
        "Discharge Date", 
        "DOD"
    ])

    # Extract Remarks
    remarks_text = None 
    boundary_marker = "For any cashless queries"
    remarks_start_match = re.search(r"Remarks\s*:", text, re.IGNORECASE)
    
    if remarks_start_match:
        remarks_content_start_index = remarks_start_match.end()
        boundary_match = re.search(boundary_marker, text[remarks_content_start_index:], re.IGNORECASE)
        
        if boundary_match:
            boundary_index_absolute = remarks_content_start_index + boundary_match.start()
            line_start_index = text.rfind("\n", 0, boundary_index_absolute)
            remarks_content_end_index = line_start_index + 1 if line_start_index != -1 else remarks_content_start_index
            if remarks_content_end_index < remarks_content_start_index:
                 remarks_content_end_index = remarks_content_start_index
            remarks_text = text[remarks_content_start_index:remarks_content_end_index].strip()
        else:
            remaining_text = text[remarks_content_start_index:]
            end_match = re.search(r"(\n\s*\n|\nNote:|\nImportant Note:|Terms and Conditions of Authorization)", remaining_text, re.IGNORECASE | re.DOTALL)
            if end_match:
                remarks_text = remaining_text[:end_match.start()].strip()
            else:
                remarks_text = remaining_text.strip()

    if not remarks_text:
        non_medical_patterns = [
            r"Non-Medical\s+Expenses.*?\(Please.*?\)(.+?)(?:\n\n|\n\s*\n|$)",
            r"Rs\.\s*([\d,]+)[-/]?\s*Deducted\s+as\s+Non\s+medical\s+expenses"
        ]
        for idx, pattern in enumerate(non_medical_patterns):
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                if idx == 0 and len(match.groups()) > 0 and match.group(1) and match.group(1).strip():
                     remarks_text = match.group(1).strip()
                elif idx == 1 and len(match.groups()) > 0 and match.group(1):
                     remarks_text = f"Rs. {match.group(1)}/- Deducted as Non medical expenses (to be borne by patient)"
                if remarks_text:
                     break

    if remarks_text:
        remarks_text = re.sub(r"\s+", " ", remarks_text).strip()
        remarks_text = re.sub(r"^[:\s-]+", "", remarks_text).strip()

    # Extract Policy Period
    policy_period = extract_policy_period(text)
    
    # Compile results for Authorization Letter
    results = {
        "Letter Type": "Authorization Letter",
        "AL Number": al_number,
        "Name of the Patient": patient_name,
        "UHID Number": uhid_number,
        "Policy No": policy_no,
        "Policy Period": policy_period,
        "Date of Admission": admission_date,
        "Date of Discharge": discharge_date,
        "Total Bill Amount": clean_number(total_amount),
        "Approved Amount": clean_number(approved_amount),
        "Remarks": remarks_text
    }
    
    return results

def preprocess_image(image):
    """Apply preprocessing to improve OCR accuracy."""
    try:
        # Convert PIL image to OpenCV format
        open_cv_image = np.array(image) 
        if len(open_cv_image.shape) == 3:
            open_cv_image = open_cv_image[:, :, ::-1].copy() # Convert RGB to BGR
        
        # Convert to grayscale
        if len(open_cv_image.shape) == 3:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = open_cv_image
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        
        # Noise removal
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Convert back to PIL format
        return Image.fromarray(opening)
    except Exception as e:
        print(f"Warning: Image preprocessing failed: {e}. Using original image.")
        return image
