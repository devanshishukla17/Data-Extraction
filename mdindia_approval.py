import camelot
import pdfplumber
import re
import json
import sys

def extract_address_layout(page):
    words = page.extract_words()
    address_lines = []
    start_y = None
    end_y = None

    for w in words:
        if w['text'].strip() == 'To,':
            start_y = w['top']
            break
    if start_y is None:
        return "null"

    for w in words:
        if w['text'].strip() in ['Phone', 'Phone:', 'Fax', 'Fax:'] and w['top'] > start_y:
            end_y = w['top']
            break
    if end_y is None:
        end_y = start_y + 150

    lines = {}
    for w in words:
        if start_y < w['top'] < end_y and w['x0'] < 250:
            y = round(w['top'], 1)
            lines.setdefault(y, []).append(w['text'])

    sorted_lines = [lines[y] for y in sorted(lines)]
    full_lines = [' '.join(line) for line in sorted_lines]
    return ', '.join(full_lines)

def extract_reason_from_pdf(pdf_path):
    try:
        tables = camelot.read_pdf(pdf_path, pages='1', flavor='stream', strip_text='\n')
        for table in tables:
            df = table.df
            if any(col.lower().replace('.','').strip() in ['srno', 'sr no'] for col in df.iloc[0]):
                for i, row in df.iterrows():
                    if str(row[0]).strip() == '1':
                        if len(row) > 1:
                            return row[1].strip()
                        else:
                            return " ".join([str(x) for x in row if str(x).strip() and not str(x).strip().isdigit()])
    except Exception as e:
        print(f"camelot error: {e}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            
            pattern1 = re.compile(r"Sr\.?No\.?\s*Particular\(s\)\s*1\s*(.+?)(?:Thanking|Authorized|$)", re.IGNORECASE | re.DOTALL)
            pattern2 = re.compile(r"Sr\s*No\.?\s*1\s*Reason\(s\)\s*(.+?)(?:Explanation|As per|$)", re.IGNORECASE | re.DOTALL)
    
            for pattern in [pattern1, pattern2]:
                match = pattern.search(text)
                if match:
                    reason = match.group(1).strip()
                    reason = ' '.join(reason.split())
                    return reason
                    
            denial_match = re.search(r"following reasons:\s*(.+?)(?:Explanation|As per|Note|$)", text, re.IGNORECASE | re.DOTALL)
            if denial_match:
                return denial_match.group(1).strip()
                
    except Exception as e:
        print(f"pdfplumber error: {e}")

    return "null"

def extract_authorization_remarks(text):
    match = re.search(r"Authorisation Remarks :(.*?)Please don't collect", text, re.DOTALL | re.IGNORECASE)
    if match:
        remarks = match.group(1).strip()
        remarks = ' '.join(remarks.split())
        return remarks
    return "null"

def extract_authorization_details(text):
    """Extracts authorization details from the table"""
    auth_details = {
        "Date and Time": {},
        "Authorized Amount": 0
    }
    
    auth_section = re.search(r"Authorization Details :(.*?)(?:\n\*\*|$)", text, re.DOTALL | re.IGNORECASE)
    if not auth_section:
        return auth_details
    
    rows = re.finditer(
        r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2}(?:AM|PM))\s+([A-Z0-9]+)\s+([\d,]+)\s+([A-Z][A-Z\s]+)",
        auth_section.group(1)
    )
    
    for row in rows:
        date = row.group(1)
        time = row.group(2)
        amount = int(row.group(4).replace(',', ''))
        status = row.group(5).strip()
        
        auth_details["Date and Time"][f"{date} {time}"] = status
        auth_details["Authorized Amount"] += amount
    
    return auth_details

def extract_table_data(text):
    data = {}
    
    # Patient Name 
    match = re.search(r"Patient Name\s*:\s*([^\n]+?)(?=\s*Age\s*:|$)", text)
    if match:
        data["Name of the Patient"] = match.group(1).strip()
    
    # Policy Number 
    match = re.search(r"Policy Number\s*:\s*([A-Za-z0-9\/-]+)", text)
    if match:
        data["Policy No"] = match.group(1).strip()
    
    # Dates 
    match = re.search(r"Expected Date of Admission\s*:\s*(\d{2}\/\d{2}\/\d{4})", text)
    if match:
        data["Date of Admission"] = match.group(1).strip()
    
    match = re.search(r"Expected Date of Discharge\s*:\s*(\d{2}\/\d{2}\/\d{4})", text)
    if match:
        data["Date of Discharge"] = match.group(1).strip()
    
    # Room Category 
    match = re.search(r"Room Category\s*:\s*([^\n]+?)(?=\s*Estimated|$)", text)
    if match:
        data["Room Category"] = match.group(1).strip()
    
    # Diagnosis 
    match = re.search(r"Provisional Diagnosis\s*:\s*([^\n]+?)(?=\s*Proposed|$)", text)
    if match:
        data["Provisional Diagnosis"] = match.group(1).strip()
    
    # Treatment 
    match = re.search(r"Proposed Line of Treatment\s*:\s*([^\n]+)", text)
    if match:
        data["Proposed Treatment"] = match.group(1).strip()
    
    return data

def extract_info_from_pdf(pdf_path):
    extracted_data = {
        "Claim Number": "null",
        "Name of the Patient": "null",
        "Policy No": "null",
        "Hospital Address": "null",
        "Rohini ID": "null",
        "Letter Type": "null",
        "MD ID No": "null",
        "Date of Admission": "null",
        "Date of Discharge": "null",
        "Room Category": "null",
        "Provisional Diagnosis": "null",
        "Proposed Treatment": "null",
        "Authorization Details": {
            "Date and Time": {},
            "Authorized Amount": 0
        },
        "Remarks": "null"
    }
     
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()

            extracted_data["Hospital Address"] = extract_address_layout(page)
            
            table_data = extract_table_data(text)
            extracted_data.update(table_data)
            
            auth_data = extract_authorization_details(text)
            extracted_data["Authorization Details"] = auth_data
            
            extracted_data["Remarks"] = extract_authorization_remarks(text)
            
            match = re.search(r"Claim\s+Number\s*:\s*([^\s\n]+)", text)
            if match:
                extracted_data["Claim Number"] = match.group(1).strip()
        
            match = re.search(r'Cashless\s+Authorisation\s+Letter', text)
            if match:
                extracted_data["Letter Type"] = "Approval"

            match = re.search(r"MD ID No\s*:\s*([^\s\n]+)", text)
            if match:
                extracted_data["MD ID No"] = match.group(1).strip()

            match = re.search(r"Rohini\s+ID\s*:\s*([^\s\n]+)", text)
            if match:
                extracted_data["Rohini ID"] = match.group(1).strip()


    except Exception as e:
        print(f"Warning: {str(e)}", file=sys.stderr)

    return extracted_data

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_pdf>")
        sys.exit(1)

    result = extract_info_from_pdf(sys.argv[1])
    print(json.dumps(result, indent=4))