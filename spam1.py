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

    # Find "To,"
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
    # First try with camelot
    try:
        tables = camelot.read_pdf(pdf_path, pages='1', flavor='stream', strip_text='\n')
        for table in tables:
            df = table.df
            # Check for either "Sr.No." or "Sr No." in header
            if any(col.lower().replace('.','').strip() in ['srno', 'sr no'] for col in df.iloc[0]):
                for i, row in df.iterrows():
                    if str(row[0]).strip() == '1':
                        # Handle both table formats
                        if len(row) > 1:
                            return row[1].strip()
                        else:
                            return " ".join([str(x) for x in row if str(x).strip() and not str(x).strip().isdigit()])
    except Exception as e:
        print(f"camelot error: {e}")

    # Fallback to pdfplumber with more flexible patterns
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            
            # Pattern for first table format (Particular(s))
            pattern1 = re.compile(r"Sr\.?No\.?\s*Particular\(s\)\s*1\s*(.+?)(?:Thanking|Authorized|$)", re.IGNORECASE | re.DOTALL)
            # Pattern for second table format (Reason(s))
            pattern2 = re.compile(r"Sr\s*No\.?\s*1\s*Reason\(s\)\s*(.+?)(?:Explanation|As per|$)", re.IGNORECASE | re.DOTALL)
    
            for pattern in [pattern1, pattern2]:
                match = pattern.search(text)
                if match:
                    reason = match.group(1).strip()
                    # Clean up extra spaces and newlines
                    reason = ' '.join(reason.split())
                    return reason
                    
            # Try to find the denial reason in the text directly
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
            match = re.search(r"Patient Name\s*:\s*([^\n]+)", text)
            if match:
                extracted_data["Name of the Patient"] = match.group(1).strip()
                
            #Type of letter
            match = re.search(r'DENIAL\s+OF\s+AUTHORIZATION\s+LETTER',text)
            if match:
                extracted_data["Letter Type"]="Authorization Denied"
            else:
                extracted_data["Letter Type"]="Query Letter"

            # Policy No
            match = re.search(r"Policy\s*No\.?\s*:\s*([^\s\n]+)", text)
            if match:
                extracted_data["Policy No"] = match.group(1).strip()

            # MDI ID No
            match = re.search(r"MDI ID No\s*:\s*([^\s\n]+)", text)
            if match:
                extracted_data["MDI ID No"] = match.group(1).strip()

            # CCN
            match = re.search(r"CCN\s*:\s*([^\s\n]+)", text)
            if match:
                extracted_data["CCN"] = match.group(1).strip()

            # Reason using camelot
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
