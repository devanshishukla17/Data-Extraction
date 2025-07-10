import pdfplumber
import re
import json
import sys

def extract_info_from_pdf(pdf_path):
    extracted_data = {
        "Claim Intimation Number": "null",
        "Name of the Insured": "null",
        "Policy Period": "null",
        "Policy Number": "null",
        "Date of Admission": "null",
        "Name of the Hospital and Location": "null"
    }

    # Define the order of fields and their stop markers
    field_order = [
        ("Claim Intimation Number", ["Name of the Insured"]),
        ("Name of the Insured", ["Age / Gender"]),
        ("Policy Number", ["Policy Period"]),
        ("Policy Period", ["Diagnosis"]),
        ("Date of Admission", ["Name of the Hospital and Location"]),
        ("Name of the Hospital and Location", ["After carefully reviewing"])
    ]

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from first page
            page = pdf.pages[0]
            text = page.extract_text()
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            current_field = None
            collected_value = []
            i = 0

            while i < len(lines):
                line = lines[i]
                
                # Check if we should start a new field
                for field, stop_markers in field_order:
                    if line.startswith(field):
                        if current_field and collected_value:
                            extracted_data[current_field] = ' '.join(collected_value).strip()
                        
                        # Start new field collection
                        current_field = field
                        collected_value = [line[len(field):].lstrip(':').strip()]
                        i += 1
                        break
                else:
                    # Check if we should stop collecting for current field
                    if current_field:
                        _, stop_markers = next((f for f in field_order if f[0] == current_field), (None, []))
                        if any(line.startswith(marker) for marker in stop_markers):
                            if collected_value:
                                extracted_data[current_field] = ' '.join(collected_value).strip()
                            current_field = None
                            collected_value = []
                            continue
                    
                    # Continue collecting for current field
                    if current_field and line:
                        collected_value.append(line)
                    i += 1

            # Save the last collected field
            if current_field and collected_value:
                extracted_data[current_field] = ' '.join(collected_value).strip()

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