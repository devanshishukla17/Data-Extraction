import pdfplumber
import re
import json
import sys

def extract_address_layout(page):
    words = page.extract_words()
    address_lines = []
    start_y = None
    end_y = None
    stop_processing = False

    # Find "To,"
    for w in words:
        if w['text'].strip() == 'To,':
            start_y = w['top']
            break
    if start_y is None:
        return "null"

    # Find end marker (Phone/Fax)
    for w in words:
        if w['text'].strip() in ['Phone', 'Phone:', 'Fax', 'Fax:'] and w['top'] > start_y:
            end_y = w['top']
            break
    if end_y is None:
        end_y = start_y + 150

    lines = {}
    for w in words:
        # Stop processing if we hit "Inlias ID"
        if 'Inlias' in w['text'] or ('ID' in w['text'] and ':' in w['text']):
            stop_processing = True
            continue
            
        if stop_processing:
            continue
            
        if start_y < w['top'] < end_y and w['x0'] < 250:
            y = round(w['top'], 1)
            lines.setdefault(y, []).append(w['text'])

    sorted_lines = [lines[y] for y in sorted(lines)]
    full_lines = [' '.join(line) for line in sorted_lines]
    
    # Join and clean the address
    address = ', '.join(full_lines)
    
    # Final cleanup to remove any trailing commas or spaces
    address = address.rstrip(', ')
    
    return address if address else "null"

def extract_reason_from_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()

            # Match line starting with 1 and followed by the reason
            reason_match = re.search(r'\b1\s+(.+?)(?=Thanking|Authorized|Explanation|As per|Note|$)', text, re.DOTALL | re.IGNORECASE)
            if reason_match:
                reason = reason_match.group(1).strip()
                reason = ' '.join(reason.split())
                return reason

            # Backup: check for "following reasons"
            denial_match = re.search(r"following reasons:\s*(.+?)(?:Explanation|As per|Note|$)", text, re.IGNORECASE | re.DOTALL)
            if denial_match:
                return denial_match.group(1).strip()

    except Exception as e:
        print(f"pdfplumber error: {e}")
    return "null"

def extract_info_from_pdf(pdf_path):
    extracted_data = {
        "Name of the Patient": "null",
        "Policy No": "null",
        "Hospital Address": "null",
        "CCN": "null",
        "Letter Type": "null",
        "MDI ID No": "null",
        "Reason": "null"
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()

            extracted_data["Hospital Address"] = extract_address_layout(page)

            # Patient Name
            match = re.search(r"Patient\s*Name\s*:\s*([^\n]+)", text, re.IGNORECASE)
            if match:
                extracted_data["Name of the Patient"] = match.group(1).strip()

            # Letter Type
            if re.search(r'DENIAL\s+OF\s+AUTHORIZATION\s+LETTER', text, re.IGNORECASE):
                extracted_data["Letter Type"] = "Authorization Denied"
            else:
                extracted_data["Letter Type"] = "Query Letter"

            # Policy No
            match = re.search(r"Policy\s*No\.?\s*:\s*([^\s\n]+)", text, re.IGNORECASE)
            if match:
                extracted_data["Policy No"] = match.group(1).strip()

            # MDI ID No - more flexible pattern
            match = re.search(r"MDI\s*(?:ID\s*No\.?)?\s*:\s*([A-Z0-9-]+)", text, re.IGNORECASE)
            if not match:
                # Try alternative pattern without colon
                match = re.search(r"MDI\s*(?:ID\s*No\.?)?\s+([A-Z0-9-]+)", text, re.IGNORECASE)
            if match:
                extracted_data["MDI ID No"] = match.group(1).strip()

            # CCN
            match = re.search(r"CCN\s*:\s*([^\s\n]+)", text, re.IGNORECASE)
            if match:
                extracted_data["CCN"] = match.group(1).strip()

            extracted_data["Reason"] = extract_reason_from_pdf(pdf_path)

    except Exception as e:
        print(f"Warning: {str(e)}", file=sys.stderr)

    return extracted_data

# CLI usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_pdf>")
        sys.exit(1)

    result = extract_info_from_pdf(sys.argv[1])
    print(json.dumps(result, indent=4))


