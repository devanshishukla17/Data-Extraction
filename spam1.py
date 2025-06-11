import fitz  # PyMuPDF
import re

def extract_text_from_pdf(pdf_path):
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_value(pattern, text, default="null"):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return default

def extract_address(text):
    if "To," in text and "Policy No" in text:
        start_idx = text.find("To,")
        end_idx = text.find("Phone")
        left_text = text[start_idx:end_idx]
        lines = [line.strip() for line in left_text.splitlines() if line.strip()]
        address_lines = []
        hospital_found = False
        for line in lines:
            if "Apollo" in line or "Hospital" in line:
                address_lines.append("Apollo Hospital")  
                hospital_found = True
            elif hospital_found:
                address_lines.append(line)
        if address_lines:
            return ', '.join(address_lines).replace("  ", " ")
    return "null"



def extract_remarks(text):
    if "For any cashless queries" in text:
        end_idx = text.find("For any cashless queries")
        relevant_text = text[:end_idx]
        # Find last paragraph block or header before it
        remarks_candidates = re.findall(r"(Remarks[\s\S]+)", relevant_text, re.IGNORECASE)
        if remarks_candidates:
            return remarks_candidates[-1].strip()
        else:
            # fallback to last few lines before marker
            lines = relevant_text.strip().splitlines()
            return "\n".join(lines[-12:]).strip()
    return "null"

def parse_pdf_data(text):
    return {
        "AL Number": extract_value(r"AL\s*Number\s*[:\-]?\s*([0-9A-Z]+)", text),
        "Approved Amount": extract_value(r"Approved\s*Amount\s*[:\-]?\s*(?:INR|Rs\.?)\s*([0-9,]+)", text),
        "Date & Time": "null",
        "Date of Admission": extract_value(r"Date\s*of\s*Admission\s*[:\-]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text),
        "Date of Discharge": extract_value(r"Date\s*of\s*Discharge\s*[:\-]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4}(?:\s*\d{1,2}:\d{2}\s*[APMapm]{2})?)", text),
        "Hospital Address": extract_address(text),
        "Letter Type": "Approval" if "Approval" in text else "null",
        "Name of the Patient": extract_value(r"Name\s*of\s*the\s*Patient\s*[:\-]?\s*([A-Za-z ]+)", text),
        "Policy No": extract_value(r"Policy\s*No\s*[:\-]?\s*([\d\-\/]+)", text),
        "Policy Period": "null",
        "Remarks": extract_remarks(text),
        "Total Bill Amount": extract_value(r"Total\s*Bill\s*Amount\s*[:\-]?\s*(?:INR|Rs\.?)\s*([0-9,.]+)", text),
        "UHID Number": extract_value(r"UHID\s*Number\s*[:\-]?\s*([0-9]+)", text)
    }

# Example usage:
pdf_path = r"C:\Desktop\INTERNSHIP\extraction\PDFs\mdindia\MDI9500361_Query_NO_0.pdf"
text = extract_text_from_pdf(pdf_path)
parsed_data = parse_pdf_data(text)

# Pretty print
import json
print(json.dumps(parsed_data, indent=4))
