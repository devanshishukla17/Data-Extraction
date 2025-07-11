import pdfplumber
import json
import sys
import io
import contextlib

def extract_info_from_pdf(pdf_path):
    extracted_data = {
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
        ("Claim Intimation Number", ["Name of the Insured"]),
        ("Name of the Insured", ["Age / Gender"]),
        ("Policy Number", ["Policy Period"]),
        ("Policy Period", ["Diagnosis"]),
        ("Date of Admission", ["Name of the Hospital and Location"]),
        ("Name of the Hospital and Location", ["After carefully reviewing"])
    ]

    try:
        # Suppress pdfplumber warnings
        with contextlib.redirect_stderr(io.StringIO()):
            with pdfplumber.open(pdf_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]

                # First determine letter type
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

                # Extract all fields using the original logic
                current_field = None
                collected_value = []
                i = 0

                while i < len(lines):
                    line = lines[i]
                    
                    # Check if we should start a new field
                    for field, stop_markers in field_order:
                        if line.startswith(field):
                            if current_field and collected_value:
                                extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()
                            
                            # Start new field collection
                            current_field = field
                            collected_value = [line[len(field):].strip()]
                            i += 1
                            break
                    else:
                        # Check if we should stop collecting for current field
                        if current_field:
                            _, stop_markers = next((f for f in field_order if f[0] == current_field), (None, []))
                            if any(line.startswith(marker) for marker in stop_markers):
                                if collected_value:
                                    extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()
                                current_field = None
                                collected_value = []
                                continue
                        
                        # Continue collecting for current field
                        if current_field and line:
                            collected_value.append(line)
                        i += 1

                # Save the last collected field
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
                        elif capture and line:  # Only add non-empty lines
                            address_lines.append(line)
                    # Join with commas and clean up any double commas
                    if address_lines:  # Only overwrite if we found an address
                        extracted_data["Name of the Hospital and Location"] = ', '.join(address_lines).replace(',,', ',').strip()

                # Extract Reason text between "required for further action." and "You can email them to"
                start_marker = "required for further action."
                end_marker = "You can email them to"
                reason_lines = []
                capture_reason = False
                
                for line in lines:
                    if start_marker in line:
                        capture_reason = True
                        # Get the part after the start marker if it's on the same line
                        parts = line.split(start_marker)
                        if len(parts) > 1:
                            reason_lines.append(parts[1].strip())
                        continue
                    elif end_marker in line:
                        # Get the part before the end marker if it's on the same line
                        parts = line.split(end_marker)
                        if parts[0].strip():
                            reason_lines.append(parts[0].strip())
                        capture_reason = False
                        break
                    elif capture_reason:
                        reason_lines.append(line.strip())
                
                if reason_lines:
                    extracted_data["Reason"] = ' '.join(reason_lines).strip()

    except Exception as e:
        print(f"Error processing PDF: {str(e)}", file=sys.stderr)

    return extracted_data

# CLI usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_pdf>")
        sys.exit(1)

    result = extract_info_from_pdf(sys.argv[1])
    print(json.dumps(result, indent=4))