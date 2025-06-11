# import pdfplumber
# import re
# import sys
# import json

# def extract_address_layout(page):
#     words = page.extract_words()
#     address_lines = []
#     start_y = None
#     end_y = None

#     # Step 1: Locate "To,"
#     for w in words:
#         if w['text'].strip() == 'To,':
#             start_y = w['top']
#             break

#     if start_y is None:
#         return "null"

#     # Step 2: Determine end y (stop near "Phone" or "Fax")
#     for w in words:
#         if w['text'].strip() in ['Phone', 'Phone:', 'Fax', 'Fax:'] and w['top'] > start_y:
#             end_y = w['top']
#             break
#     if end_y is None:
#         end_y = start_y + 150  # fallback limit

#     # Step 3: Collect words on the left side only
#     lines = {}
#     for w in words:
#         if start_y < w['top'] < end_y and w['x0'] < 250:  # left side only
#             y = round(w['top'], 1)
#             lines.setdefault(y, []).append(w['text'])

#     if not lines:
#         return "null"

#     # Step 4: Combine lines and return
#     sorted_lines = [lines[y] for y in sorted(lines)]
#     full_lines = [' '.join(line) for line in sorted_lines]
#     return ', '.join(full_lines)

# def extract_info_from_pdf(pdf_path):
#     extracted_data = {
#         "Name of the Patient": "null",
#         "Policy No": "null",
#         "Hospital Address": "null",
#         "CCN": "null",
#         "Letter Type": "Denial",
#         "MDI ID No": "null",
#         "Reason": "null"
#     }

#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             page = pdf.pages[0]
#             text = page.extract_text()

#             # Extract address using layout
#             extracted_data["Hospital Address"] = extract_address_layout(page)

#             # Patient Name
#             match = re.search(r"Patient Name\s*:\s*([^\n]+)", text)
#             if match:
#                 extracted_data["Name of the Patient"] = match.group(1).strip()

#             # Policy No
#             match = re.search(r"Policy\s*No\.?\s*:\s*([^\s\n]+)", text)
#             if match:
#                 extracted_data["Policy No"] = match.group(1).strip()

#             # MDI ID No
#             match = re.search(r"MDI ID No\s*:\s*([^\s\n]+)", text)
#             if match:
#                 extracted_data["MDI ID No"] = match.group(1).strip()

#             # CCN
#             match = re.search(r"CCN\s*:\s*([^\s\n]+)", text)
#             if match:
#                 extracted_data["CCN"] = match.group(1).strip()

#             # Reason
#             match = re.search(r"1\s+(The Cashless Hospitalization.*?cannot be Ascertained\.)", text, re.IGNORECASE)
#             if match:
#                 extracted_data["Reason"] = match.group(1).strip()

#     except Exception as e:
#         print(f"Warning: {str(e)}", file=sys.stderr)

#     return extracted_data

# if __name__ == "__main__":
#     if len(sys.argv) != 2:
#         print("Usage: python script.py <path_to_pdf>")
#         sys.exit(1)

#     result = extract_info_from_pdf(sys.argv[1])
#     print(json.dumps(result, indent=4))


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
    # Try camelot first
    try:
        import camelot
        tables = camelot.read_pdf(pdf_path, pages='1', flavor='stream', strip_text='\n')
        for table in tables:
            df = table.df
            for i, row in df.iterrows():
                if row[0].strip() == '1' or row[0].strip().lower().startswith("1"):
                    return row[1].strip()
    except Exception as e:
        print(f"camelot error: {e}")

    # Fallback to text pattern if table detection fails
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            reason_block = re.search(r"Sr\s*No\.\s*Reason\(s\)\s*1\s*(.+?)(?:Explanation|As per|Note)", text, re.IGNORECASE | re.DOTALL)
            if reason_block:
                return reason_block.group(1).strip().replace('\n', ' ')
    except Exception as e:
        print(f"text fallback error: {e}")

    return "null"



def extract_info_from_pdf(pdf_path):
    extracted_data = {
        "Name of the Patient": "null",
        "Policy No": "null",
        "Hospital Address": "null",
        "CCN": "null",
        "Letter Type": "Denial",
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
