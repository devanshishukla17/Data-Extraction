import pdfplumber
import json
import sys
import io
import contextlib
import re

def extract_info_from_pdf(pdf_path):
    extracted_data = {
        "UIN No.": "null",
        "Claim Intimation Number": "null",
        "Name of the Insured": "null",
        "Policy Period": "null",
        "Policy Number": "null",
        "Date of Admission": "null",
        "Name of the Hospital and Location": "null",
        "Letter Type": "null",
        "Reason": "null"
    }

    field_order = [
        ("Claim Intimation Number", ["Name of the Insured", "Product Name"]),
        ("Name of the Insured", ["Age / Gender", "Age/Gender"]),
        ("Policy Number", ["Policy Period"]),
        ("Policy No.", ["Policy Period"]),
        ("Policy Period", ["Diagnosis"]),
        ("Date of Admission", ["Room Category"]),
        ("Name of the Hospital and Location", ["After carefully reviewing", "Room Category"]),
        ("UIN No.", ["Policy No.", "Policy Number"])
    ]

    try:
        with contextlib.redirect_stderr(io.StringIO()):
            with pdfplumber.open(pdf_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                is_denial = False
                for line in lines[:10]:
                    if "Unable to Admit Claim" in line:
                        extracted_data["Letter Type"] = "Denial Letter"
                        is_denial = True
                        break
                    elif "Pre-Authorisation Query" in line:
                        extracted_data["Letter Type"] = "Query Letter"
                        break
                else:
                    extracted_data["Letter Type"] = "Unknown Letter Type"

                current_field = None
                collected_value = []
                i = 0

                while i < len(lines):
                    line = lines[i]
                    
                    if is_denial and line.startswith("Policy No."):
                        if current_field and collected_value:
                            extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()
                        current_field = "Policy Number"
                        collected_value = [line[len("Policy No."):].strip()]
                        i += 1
                        continue
                    
                    for field, stop_markers in field_order:
                        if line.startswith(field):
                            if current_field and collected_value:
                                extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()
                            
                            current_field = field if field != "Policy No." else "Policy Number"
                            collected_value = [line[len(field):].strip()]
                            i += 1
                            break
                    else:
                        if current_field:
                            _, stop_markers = next((f for f in field_order if f[0] == current_field), (None, []))
                            if any(line.startswith(marker) for marker in stop_markers):
                                if collected_value:
                                    extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()
                                current_field = None
                                collected_value = []
                                continue
                        
                        if current_field and line:
                            collected_value.append(line)
                        i += 1

                if current_field and collected_value:
                    extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()

                if is_denial:
                    address_lines = []
                    capture = False
                    for line in lines:
                        if line.startswith("To"):
                            capture = True
                            continue
                        elif line.startswith("Dear Sir/Madam,"):
                            break
                        elif capture and line:
                            address_lines.append(line)
                    if address_lines:
                        extracted_data["Name of the Hospital and Location"] = ', '.join(address_lines).replace(',,', ',').strip()

                #Reason for denial letters
                if is_denial:
                    start_marker = "We regret we are unable to admit the claim"
                    end_marker = "If you have any questions"
                    reason_lines = []
                    capturing = False
                    footer_keywords = [
                        "Star Health and Allied Insurance",
                        "Customer Care:",
                        "IRDAI Registration No:",
                        "www.starhealth.in",
                        "Corporate Customer Care:",
                        "WhatsApp:",
                        "Email: support@starhealth.in",
                        "Balaji Complex"
                    ]
                    
                    for line in lines:
                        if start_marker in line:
                            capturing = True
                            continue
                        elif end_marker in line:
                            break
                        elif capturing:
                            if not any(keyword in line for keyword in footer_keywords):
                                if not re.match(r'^\d+$', line.strip()):
                                    reason_lines.append(line.strip())
                    
                    if reason_lines:
                        reason_text = '\n'.join(reason_lines).strip()
                        reason_text = re.sub(r'\n\d+$', '', reason_text)
                        extracted_data["Reason"] = reason_text

                else:
                    start_marker = "required for further action."
                    end_marker = "You can email them to"
                    reason_lines = []
                    capture_reason = False
                    
                    for line in lines:
                        if start_marker in line:
                            capture_reason = True
                            parts = line.split(start_marker)
                            if len(parts) > 1:
                                reason_lines.append(parts[1].strip())
                            continue
                        elif end_marker in line:
                            parts = line.split(end_marker)
                            if parts[0].strip():
                                reason_lines.append(parts[0].strip())
                            capture_reason = False
                            break
                        elif capture_reason:
                            reason_lines.append(line.strip())
                    
                    if reason_lines:
                        extracted_data["Reason"] = ' '.join(reason_lines).strip()

                if extracted_data["Letter Type"] == "Query Letter":
                    extracted_data.pop("UIN No.", None)
                elif extracted_data["Letter Type"] == "Denial Letter":
                    required_fields = [
                        "UIN No.",
                        "Claim Intimation Number",
                        "Name of the Insured",
                        "Policy Period",
                        "Policy Number",
                        "Date of Admission",
                        "Name of the Hospital and Location",
                        "Letter Type",
                        "Reason"                        
                    ]
                    for field in list(extracted_data.keys()):
                        if field not in required_fields:
                            extracted_data.pop(field, None)

    except Exception as e:
        print(f"Error processing PDF: {str(e)}", file=sys.stderr)

    return extracted_data

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_pdf>")
        sys.exit(1)

    result = extract_info_from_pdf(sys.argv[1])
    print(json.dumps(result, indent=4))