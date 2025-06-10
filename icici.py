from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_path
import fitz  # PyMuPDF
import re
from datetime import datetime
import os
import base64
from io import BytesIO
from PIL import Image
import numpy as np
import cv2

app = Flask(__name__)

def normalize_text(s):
    """Normalize text by replacing special characters and whitespace."""
    if s is None:
        return None
    return s.replace('\u00A0', ' ').replace('­', '-').replace('–', '-').replace('—', '-').strip()

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

def is_scanned_pdf(pdf_stream):
    """Determine if a PDF is scanned (image-based) or contains extractable text."""
    try:
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        text_content = ""
        for page in doc:
            text_content += page.get_text()
        doc.close()
        
        # If there's very little text or no text, it's likely a scanned PDF
        if len(text_content.strip()) < 100:
            return True
        return False
    except Exception as e:
        print(f"Error checking PDF type: {e}")
        # Default to treating as scanned if we can't determine
        return True

def identify_letter_type(text):
    """Identify letter type based on the first few lines of text."""
    # Extract first few lines
    lines = text.split('\n')
    first_lines = ' '.join(lines[:20])  # Consider first 20 lines to catch the title
    
    # Check for authorization letter
    if re.search(r"Authorization\s+Letter\s+to\s+the\s+Hospital", first_lines, re.IGNORECASE):
        return "Authorization Letter"
    
    # Check for query letter
    if re.search(r"ADDITIONAL\s+INFORMATION\s+REQUEST\s+FORM", first_lines, re.IGNORECASE):
        return "Query Letter"
    
    # Check for denied letter
    if re.search(r"DENIAL\s+OF\s+CASHLESS\s+ACCESS", first_lines, re.IGNORECASE) or re.search(r"Rejection\s+Letter", first_lines, re.IGNORECASE):
        return "Denied Letter"
    
    # Default if no specific type is identified
    if "Authorization Letter" in text:
        return "Authorization Letter"
    elif "Query" in text or "Information Request" in text or "ADDITIONAL INFORMATION" in text:
        return "Query Letter"
    elif "Denied" in text or "Denial" in text or "DENIAL" in text or "Rejection" in text:
        return "Denied Letter"
    
    return "Unknown Letter Type"

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

def extract_query_letter_fields(text, with_ocr=False):
    """Extract fields specific to Query Letter."""
    # Extract patient name (Claim of)
    patient_name = None
    name_patterns = [
        r"Claim\s+of\s*:?\s*([^\n]+)",
        r"Claim\s+of\s+([^\n]+)",
        r"Name\s+of\s+the\s+Patient\s*:\s*([^\n]+)",
        r"Patient\s+Name\s*:\s*([^\n]+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            patient_name = match.group(1).strip()
            break
    
    # Extract UHID
    uhid_number = None
    uhid_patterns = [
        r"UHID\s*:?\s*([^\n]+)",
        r"UHID\s+([^\n]+)",
        r"UHID\s*Number\s*:\s*([^\n]+)"
    ]
    
    for pattern in uhid_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            uhid_number = match.group(1).strip()
            break
    
    # Extract Policy Number
    policy_no = None
    policy_patterns = [
        r"Policy\s*Number\s*:?\s*([^\n]+)",
        r"Policy\s*No\s*:?\s*([^\n]+)",
        r"Policy\s*Number\s+([^\n]+)"
    ]
    
    for pattern in policy_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            policy_no = match.group(1).strip()
            break
    
    # Extract Policy Period with improved handling for multi-line periods
    policy_period = extract_policy_period(text)
    
    # Extract Date of Admission
    admission_date = None
    date_patterns = [
        r"Date\s+of\s+Admission\s*:?\s*([^\n]+)",
        r"Admission\s+Date\s*:?\s*([^\n]+)",
        r"DOA\s*:?\s*([^\n]+)"
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            admission_date = match.group(1).strip()
            break
    
    # Extract AL Number
    al_number = None
    al_patterns = [
        r"AL\s*Number\s*:?\s*([^\n]+)",
        r"AL\s*No\s*:?\s*([^\n]+)",
        r"AL\s*Number\s+([^\n]+)"
    ]
    
    for pattern in al_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            al_number = match.group(1).strip()
            break
    
    # Extract Reasons from table - ONLY THE REASON COLUMN
    remarks_section = ""
    remarks_match = re.search(r"REMARKS\s*:(.+?)(?:Any\s+Other\s+document|We\s+request\s+you|$)", text, re.IGNORECASE | re.DOTALL)
    if remarks_match:
        remarks_section = remarks_match.group(1).strip()
    
    reasons = []
    
    table_header_match = re.search(r"Sr\s*No\s*Query\s*Description", remarks_section, re.IGNORECASE)
    if table_header_match:
        table_text = remarks_section[table_header_match.end():]
        reason_matches = re.findall(r"(\d+)\s+([^0-9\n]+?)(?=\s+\d+\.\s+|\n\s*\d+\s+|Description|\n\n|$)", table_text)
        
        for num, reason in reason_matches:
            reason = reason.strip()
            if reason and len(reason) > 3:
                if "Description" in reason:
                    reason = reason.split("Description")[0].strip()
                reasons.append(f"{num}. {reason}")
    
    if not reasons:
        common_queries = [
            "Past Medical/Surgical History",
            "Documents not received",
            "Investigation Reports",
            "Case Summary",
            "Indoor Case Papers"
        ]
        
        for i, query in enumerate(common_queries, 1):
            if query in text:
                reasons.append(f"{i}. {query}")
    
    if not reasons:
        lines = remarks_section.split('\n')
        current_num = None
        current_reason = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            num_match = re.match(r"^\s*(\d+)\s+(.+)$", line)
            if num_match:
                if current_num and current_reason:
                    reasons.append(f"{current_num}. {current_reason}")
                
                current_num = num_match.group(1)
                current_reason = num_match.group(2).strip()
                
                if "Description" in current_reason:
                    current_reason = current_reason.split("Description")[0].strip()
            
            if "Any Other document" in line or "We request you" in line:
                if current_num and current_reason:
                    reasons.append(f"{current_num}. {current_reason}")
                break
    
    if reasons and not any(r.startswith("1.") for r in reasons):
        first_reason_match = re.search(r"1\s+([^0-9\n]+?)(?=\s+2\s+|\n\s*2\s+|Description|\n\n|$)", remarks_section)
        if first_reason_match:
            first_reason = first_reason_match.group(1).strip()
            if "Description" in first_reason:
                first_reason = first_reason.split("Description")[0].strip()
            reasons.insert(0, f"1. {first_reason}")
    
    if reasons and not any(r.startswith("1.") for r in reasons):
        for i, line in enumerate(text.split('\n')):
            if "Past Medical" in line or "Medical History" in line:
                reasons.insert(0, "1. Past Medical/Surgical History")
                break
    
    if reasons:
        sorted_reasons = []
        for i in range(1, 6):
            reason_found = False
            for r in reasons:
                if r.startswith(f"{i}."):
                    sorted_reasons.append(r)
                    reason_found = True
                    break
            
            if not reason_found and any(r.startswith(f"{j}.") for j in range(i+1, 6) for r in reasons):
                common_reasons = {
                    1: "Past Medical/Surgical History",
                    2: "Documents not received",
                    3: "Investigation Reports",
                    4: "Case Summary",
                    5: "Indoor Case Papers"
                }
                
                if i in common_reasons:
                    sorted_reasons.append(f"{i}. {common_reasons[i]}")
        
        if sorted_reasons:
            reasons = sorted_reasons
    
    # Compile results for Query Letter
    results = {
        "Letter Type": "Query Letter",
        "Name of the Patient": patient_name,
        "UHID Number": uhid_number,
        "Policy No": policy_no,
        "Policy Period": policy_period,
        "Date of Admission": admission_date,
        "AL Number": al_number,
        "Reason": "\n".join(reasons) if reasons else None
    }
    
    return results

def extract_denied_letter_fields(text, with_ocr=False):
    """Extract fields specific to Denied Letter."""
    # Extract patient name (Claim of)
    patient_name = None
    name_patterns = [
        r"Claim\s+of\s*:?\s*([^\n]+)",
        r"Claim\s+of\s+([^\n]+)",
        r"Name\s+of\s+the\s+Patient\s*:\s*([^\n]+)",
        r"Patient\s+Name\s*:\s*([^\n]+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            patient_name = match.group(1).strip()
            break
    
    # Extract UHID
    uhid_number = None
    uhid_patterns = [
        r"UHID\s*:?\s*([^\n]+)",
        r"UHID\s+([^\n]+)",
        r"UHID\s*Number\s*:\s*([^\n]+)"
    ]
    
    for pattern in uhid_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            uhid_number = match.group(1).strip()
            break
    
    # Extract Policy Number
    policy_no = None
    policy_patterns = [
        r"Policy\s*Number\s*:?\s*([^\n]+)",
        r"Policy\s*No\s*:?\s*([^\n]+)",
        r"Policy\s*Number\s+([^\n]+)"
    ]
    
    for pattern in policy_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            policy_no = match.group(1).strip()
            break
    
    # Extract Policy Period with improved handling for multi-line periods
    policy_period = extract_policy_period(text)
    
    # Extract AL Number
    al_number = None
    al_patterns = [
        r"AL\s*Number\s*:?\s*([^\n]+)",
        r"AL\s*No\s*:?\s*([^\n]+)",
        r"AL\s*Number\s+([^\n]+)"
    ]
    
    for pattern in al_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            al_number = match.group(1).strip()
            break
    
    # Extract Reasons from table - ONLY THE REASON COLUMN
    reasons = []
    
    reason_section = ""
    reason_match = re.search(r"mentioned\s+herein\s+below(.+?)(?:Important\s+Note|$)", text, re.IGNORECASE | re.DOTALL)
    if reason_match:
        reason_section = reason_match.group(1).strip()
    
    table_header_match = re.search(r"Sr\s*No\s*Reason\s*Description", reason_section, re.IGNORECASE)
    if table_header_match:
        table_text = reason_section[table_header_match.end():]
        reason_matches = re.findall(r"(\d+)\s+([^0-9\n]+?)(?=\s+\d+\.\s+|\n\s*\d+\s+|Description|\n\n|$)", table_text)
        
        for num, reason in reason_matches:
            reason = reason.strip()
            if reason and len(reason) > 3:
                if "Description" in reason:
                    reason = reason.split("Description")[0].strip()
                reasons.append(f"{num}. {reason}")
    
    if not reasons:
        lines = text.split('\n')
        current_num = None
        current_reason = None
        in_table = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if "Sr No" in line and "Reason" in line and "Description" in line:
                in_table = True
                continue
            
            if in_table:
                num_match = re.match(r"^\s*(\d+)\s+(.+)$", line)
                if num_match:
                    if current_num and current_reason:
                        reasons.append(f"{current_num}. {current_reason}")
                    
                    current_num = num_match.group(1)
                    current_reason = num_match.group(2).strip()
                    
                    if "Description" in current_reason:
                        current_reason = current_reason.split("Description")[0].strip()
                
                if "Important Note" in line or "Note:" in line:
                    if current_num and current_reason:
                        reasons.append(f"{current_num}. {current_reason}")
                    break
    
    if not reasons:
        for i, line in enumerate(text.split('\n')):
            if "General Terms" in line or "Pre-Existing" in line or "Exclusion" in line:
                reason_text = line.strip()
                if "Description" in reason_text:
                    reason_text = reason_text.split("Description")[0].strip()
                if reason_text and len(reason_text) > 10:
                    reasons.append(f"1. {reason_text}")
                    break
    
    # Compile results for Denied Letter
    results = {
        "Letter Type": "Denied Letter",
        "Name of the Patient": patient_name,
        "UHID Number": uhid_number,
        "Policy No": policy_no,
        "Policy Period": policy_period,
        "AL Number": al_number,
        "Reason": "\n".join(reasons) if reasons else None
    }
    
    return results

def extract_fields_from_text(text, with_ocr=False):
    """Extract fields from text content based on letter type."""
    text = normalize_text(text)
    
    # Identify letter type
    letter_type = identify_letter_type(text)
    
    # Extract fields based on letter type
    if letter_type == "Authorization Letter":
        return extract_authorization_letter_fields(text, with_ocr)
    elif letter_type == "Query Letter":
        return extract_query_letter_fields(text, with_ocr)
    elif letter_type == "Denied Letter":
        return extract_denied_letter_fields(text, with_ocr)
    else:
        return extract_authorization_letter_fields(text, with_ocr)

def extract_from_printed_pdf(pdf_stream):
    """Extract text from a printed PDF with extractable text."""
    try:
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        
        return extract_fields_from_text(text, with_ocr=False)
    except Exception as e:
        print(f"Error extracting from printed PDF: {e}")
        return {"error": str(e)}

def extract_from_scanned_pdf(pdf_stream, preprocess=False):
    """Extract text from a scanned PDF using OCR."""
    try:
        # Save the stream to a temporary file (pdf2image requires a file path)
        with open("temp.pdf", "wb") as f:
            f.write(pdf_stream.getbuffer())
        
        # Convert PDF to images
        images = convert_from_path("temp.pdf")
        
        # Remove temporary file
        os.remove("temp.pdf")
        
        # Extract text from each page using OCR
        full_text = ""
        for i, image in enumerate(images):
            if preprocess:
                processed_image = preprocess_image(image)
            else:
                processed_image = image
            
            page_text = pytesseract.image_to_string(
                processed_image, 
                lang='eng',
                config='--oem 3 --psm 6'
            )
            full_text += page_text + "\n\n"
        
        return extract_fields_from_text(full_text, with_ocr=True)
    except Exception as e:
        print(f"Error extracting from scanned PDF: {e}")
        return {"error": str(e)}

def extract_from_image(image_stream, preprocess=False):
    """Extract text from an image file using OCR."""
    try:
        image = Image.open(image_stream)
        
        if preprocess:
            processed_image = preprocess_image(image)
        else:
            processed_image = image
        
        text = pytesseract.image_to_string(
            processed_image, 
            lang='eng',
            config='--oem 3 --psm 6'
        )
        
        return extract_fields_from_text(text, with_ocr=True)
    except Exception as e:
        print(f"Error extracting from image: {e}")
        return {"error": str(e)}

def extract_from_stream(file_stream, file_type, preprocess=False):
    """Extract information from a file stream."""
    if file_type == 'pdf':
        if is_scanned_pdf(file_stream):
            return extract_from_scanned_pdf(file_stream, preprocess)
        else:
            return extract_from_printed_pdf(file_stream)
    elif file_type in ['png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'gif']:
        return extract_from_image(file_stream, preprocess)
    else:
        return {"error": f"Unsupported file format: {file_type}"}

@app.route('/api/extract', methods=['POST'])
def api_extract():
    try:
        data = request.get_json()

        if not data or 'document' not in data or not data['document']:
            return jsonify({"error": "Missing or invalid 'document' field"}), 400

        file_content_base64 = data['document'][0].get('fileContent')
        if not file_content_base64:
            return jsonify({"error": "Missing 'fileContent' in document"}), 400

        file_name = data['document'][0].get('fileName', '')
        file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
        
        # Decode base64 content
        file_bytes = base64.b64decode(file_content_base64)
        file_stream = BytesIO(file_bytes)
        
        # Determine file type
        if file_ext in ['pdf']:
            file_type = 'pdf'
        elif file_ext in ['png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'gif']:
            file_type = file_ext
        else:
            return jsonify({"error": "Unsupported file type"}), 400
        
        # Get preprocessing flag (default to False)
        preprocess = data.get('preprocess', False)
        
        # Process the file
        result = extract_from_stream(file_stream, file_type, preprocess)
        
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)