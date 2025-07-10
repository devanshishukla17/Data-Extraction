# import pdfplumber
# import json
# import sys
# import io
# import contextlib

# def extract_info_from_pdf(pdf_path):
#     extracted_data = {
#         "Claim Intimation Number": "null",
#         "Name of the Insured": "null",
#         "Policy Period": "null",
#         "Policy Number": "null",
#         "Date of Admission": "null",
#         "Name of the Hospital and Location": "null",
#         "Letter Type": "null",
#         "Date & Time": "null"
#     }

#     field_order = [
#         ("Claim Intimation Number", ["Name of the Insured"]),
#         ("Name of the Insured", ["Age / Gender"]),
#         ("Policy Number", ["Policy Period"]),
#         ("Policy Period", ["Diagnosis"]),
#         ("Date of Admission", ["Name of the Hospital and Location"]),
#         ("Name of the Hospital and Location", ["After carefully reviewing"])
#     ]

#     try:
#         # Suppress pdfplumber warnings
#         with contextlib.redirect_stderr(io.StringIO()):
#             with pdfplumber.open(pdf_path) as pdf:
#                 # First determine letter type from initial lines
#                 first_page = pdf.pages[0]
#                 first_lines = "\n".join([line.strip() for line in first_page.extract_text().split('\n')[:10]])
                
#                 if "Pre-Authorisation Query" in first_lines:
#                     extracted_data["Letter Type"] = "Query Letter"
#                 elif "Unable to Admit Claim" in first_lines:
#                     extracted_data["Letter Type"] = "Denial Letter"
#                 else:
#                     extracted_data["Letter Type"] = "Unknown Letter Type"

#                 # Now extract the other fields
#                 text = first_page.extract_text()
#                 lines = [line.strip() for line in text.split('\n') if line.strip()]

#                 current_field = None
#                 collected_value = []
#                 i = 0

#                 while i < len(lines):
#                     line = lines[i]
                    
#                     # Check if we should start a new field
#                     for field, stop_markers in field_order:
#                         if line.startswith(field):
#                             if current_field and collected_value:
#                                 extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()
                            
#                             # Start new field collection
#                             current_field = field
#                             collected_value = [line[len(field):].strip()]
#                             i += 1
#                             break
#                     else:
#                         # Check if we should stop collecting for current field
#                         if current_field:
#                             _, stop_markers = next((f for f in field_order if f[0] == current_field), (None, []))
#                             if any(line.startswith(marker) for marker in stop_markers):
#                                 if collected_value:
#                                     extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()
#                                 current_field = None
#                                 collected_value = []
#                                 continue
                        
#                         # Continue collecting for current field
#                         if current_field and line:
#                             collected_value.append(line)
#                         i += 1

#                 # Save the last collected field
#                 if current_field and collected_value:
#                     extracted_data[current_field] = ' '.join(collected_value).strip().lstrip(':').strip()

#     except Exception as e:
#         print(f"Error processing PDF: {str(e)}", file=sys.stderr)

#     return extracted_data

# # CLI usage
# if __name__ == "__main__":
#     if len(sys.argv) != 2:
#         print("Usage: python script.py <path_to_pdf>")
#         sys.exit(1)

#     result = extract_info_from_pdf(sys.argv[1])
#     print(json.dumps(result, indent=4))

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
        "Date & Time": "null"
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

                # First determine letter type and extract date/time
                for i, line in enumerate(lines[:10]):  # Check first 10 lines
                    if "Pre-Authorisation Query" in line:
                        extracted_data["Letter Type"] = "Query Letter"
                        # Look for date and time in next few lines
                        for j in range(i, min(i+5, len(lines))):
                            if "Date :" in lines[j] and "Time :" in lines[j]:
                                parts = lines[j].split("Time :")
                                date_part = parts[0].replace("Date :", "").strip()
                                time_part = parts[1].strip()
                                extracted_data["Date & Time"] = f"{date_part} {time_part}"
                                break
                            elif "Date :" in lines[j] and j+1 < len(lines) and "Time :" in lines[j+1]:
                                date_part = lines[j].replace("Date :", "").strip()
                                time_part = lines[j+1].replace("Time :", "").strip()
                                extracted_data["Date & Time"] = f"{date_part} {time_part}"
                                break
                        break
                    elif "Unable to Admit Claim" in line:
                        extracted_data["Letter Type"] = "Denial Letter"
                        # Look for date and time in next few lines
                        for j in range(i, min(i+5, len(lines))):
                            if "Date :" in lines[j] and "Time :" in lines[j]:
                                parts = lines[j].split("Time :")
                                date_part = parts[0].replace("Date :", "").strip()
                                time_part = parts[1].strip()
                                extracted_data["Date & Time"] = f"{date_part} {time_part}"
                                break
                            elif "Date :" in lines[j] and j+1 < len(lines) and "Time :" in lines[j+1]:
                                date_part = lines[j].replace("Date :", "").strip()
                                time_part = lines[j+1].replace("Time :", "").strip()
                                extracted_data["Date & Time"] = f"{date_part} {time_part}"
                                break
                        break

                # Now extract the other fields using existing logic
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