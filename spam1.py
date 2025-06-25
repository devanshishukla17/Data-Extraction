# import pdfplumber
# import re
# import json
# import sys

# def suppress_warnings():
#     # Suppress the CropBox warnings
#     import warnings
#     warnings.filterwarnings("ignore", message="CropBox missing from /Page, defaulting to MediaBox")

# def extract_hospital_address(page):
#     words = page.extract_words()
#     address_lines = []
#     start_y = None
#     end_y = None

#     # Look for the hospital name which appears just before the address
#     for i, w in enumerate(words):
#         if "HOSPITAL" in w['text'].upper():
#             start_y = w['top']
#             break
    
#     if start_y is None:
#         return "null"

#     # Find the end of the address (before the city name repeats)
#     for w in words[i+1:]:
#         if w['text'].strip().isdigit() and len(w['text'].strip()) == 6:  # PIN code detection
#             end_y = w['top'] + 20
#             break
#     if end_y is None:
#         end_y = start_y + 150

#     lines = {}
#     for w in words:
#         if start_y < w['top'] < end_y and w['x0'] < 250:
#             y = round(w['top'], 1)
#             lines.setdefault(y, []).append(w['text'])

#     sorted_lines = [lines[y] for y in sorted(lines)]
#     full_lines = [' '.join(line) for line in sorted_lines]
#     return ', '.join(full_lines).replace(',,', ',')

# def extract_info_from_pdf(pdf_path):
#     suppress_warnings()
    
#     extracted_data = {
#         "AL Number": "null",
#         "Approved Amount": "null",
#         "Date & Time": "null",
#         "Date of Admission": "null",
#         "Date of Discharge": "null",
#         "Hospital Address": "null",
#         "Letter Type": "Approval",
#         "Name of the Patient": "null",
#         "Policy No": "null",
#         "Policy Period": "null",
#         "Remarks": "null",
#         "Total Bill Amount": "null",
#         "UHID Number": "null"
#     }
     
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             page = pdf.pages[0]
#             text = page.extract_text()

#             # Extract Hospital Address
#             extracted_data["Hospital Address"] = extract_hospital_address(page)
            
#             # Extract AL Number (Claim Number)
#             al_match = re.search(r"Claim Number AL:\s*([^\s\n]+)", text)
#             if al_match:
#                 extracted_data["AL Number"] = al_match.group(1).strip('()')
            
#             # Extract Patient Name
#             patient_match = re.search(r"Patient Name\s*:\s*([^\n]+?)(?=\s*Age\s*:|$)", text)
#             if patient_match:
#                 extracted_data["Name of the Patient"] = patient_match.match.group(1).strip()
            
#             # Extract Policy Number
#             policy_match = re.search(r"Policy No\s*:\s*([A-Za-z0-9\/-]+)", text)
#             if policy_match:
#                 extracted_data["Policy No"] = policy_match.group(1).strip()
            
#             # Extract Policy Period
#             period_match = re.search(r"Policy period\s*:\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})", text, re.IGNORECASE)
#             if period_match:
#                 extracted_data["Policy Period"] = f"{period_match.group(1).strip()} To {period_match.group(2).strip()}"
            
#             # Extract Dates
#             admission_match = re.search(r"Expected Date of Admission\s*:\s*(\d{2}-\w{3}-\d{4})", text)
#             if admission_match:
#                 extracted_data["Date of Admission"] = admission_match.group(1).strip()
            
#             discharge_match = re.search(r"Expected Date of Discharge\s*:\s*(\d{2}-\w{3}-\d{4})", text)
#             if discharge_match:
#                 extracted_data["Date of Discharge"] = discharge_match.group(1).strip()
            
#             # Extract Authorization Details
#             auth_match = re.search(r"Authorization Details:\s*(\d{2}/\w{3}/\d{4}\s+\d{1,2}:\d{2}:\d{2})\s+([^\s]+)\s+([\d,]+\.\d{2})", text)
#             if auth_match:
#                 extracted_data["Date & Time"] = auth_match.group(1).strip()
#                 extracted_data["Approved Amount"] = auth_match.group(3).strip()
            
#             # Extract Remarks
#             remarks_match = re.search(r"Authorization remarks\s*:\s*(.*?)(?:\n\n|\n\*|$)", text, re.DOTALL | re.IGNORECASE)
#             if remarks_match:
#                 extracted_data["Remarks"] = remarks_match.group(1).strip()
            
#             # Extract Total Bill Amount
#             bill_match = re.search(r"Total Bill Amount\s*([\d,]+\.\d{2})", text)
#             if bill_match:
#                 extracted_data["Total Bill Amount"] = bill_match.group(1).strip()
            
#             # Extract UHID Number (assuming this is the Rohini ID)
#             uhid_match = re.search(r"Rohini ID\s*:\s*([^\s\n]+)", text)
#             if uhid_match:
#                 extracted_data["UHID Number"] = uhid_match.group(1).strip()

#     except Exception as e:
#         print(f"Error processing PDF: {str(e)}", file=sys.stderr)

#     return extracted_data

# if __name__ == "__main__":
#     if len(sys.argv) != 2:
#         print("Usage: python script.py <path_to_pdf>")
#         sys.exit(1)

#     result = extract_info_from_pdf(sys.argv[1])
#     print(json.dumps(result, indent=4))

# import pdfplumber
# import re
# import json
# import sys

# def suppress_warnings():
#     import warnings
#     warnings.filterwarnings("ignore", message="CropBox missing from /Page, defaulting to MediaBox")

# def extract_info_from_pdf(pdf_path):
#     suppress_warnings()
    
#     extracted_data = {
#         "Name of the Patient": "null",
#         "Policy No": "null",
#         "Policy Period": "null",
#         "Date of Admission": "null",
#         "Date of Discharge": "null"
#     }

#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             page = pdf.pages[0]
#             text = page.extract_text()

#             # More precise Patient Name extraction
#             patient_match = re.search(
#                 r"Patient\s*Name\s*:\s*([A-Z][^\n]+?)\s*(?:\n|Age\s*:|$)", 
#                 text, 
#                 re.DOTALL
#             )
#             if patient_match:
#                 name = ' '.join(patient_match.group(1).strip().split())
#                 extracted_data["Name of the Patient"] = name

#             # Policy Number
#             policy_match = re.search(r"Policy\s*No\s*:\s*([A-Z0-9]+)", text)
#             if policy_match:
#                 extracted_data["Policy No"] = policy_match.group(1).strip()

#             # Policy Period
#             period_match = re.search(
#                 r"Policy\s*period\s*:\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})", 
#                 text
#             )
#             if period_match:
#                 extracted_data["Policy Period"] = f"{period_match.group(1)} To {period_match.group(2)}"

#             # Date of Admission - more specific pattern
#             admission_match = re.search(
#                 r"Expected\s*Date\s*of\s*Admission\s*:\s*(\d{2}-\w{3}-\d{4})", 
#                 text
#             )
#             if not admission_match:
#                 admission_match = re.search(
#                     r"Expected\s*Date\s*of\s*Admission\s*:\s*\n\s*(\d{2}-\w{3}-\d{4})", 
#                     text
#                 )
#             if admission_match:
#                 extracted_data["Date of Admission"] = admission_match.group(1)

#             # Date of Discharge - more specific pattern
#             discharge_match = re.search(
#                 r"Expected\s*Date\s*of\s*Discharge\s*:\s*(\d{2}-\w{3}-\d{4})", 
#                 text
#             )
#             if not discharge_match:
#                 discharge_match = re.search(
#                     r"Expected\s*Date\s*of\s*Discharge\s*:\s*\n\s*(\d{2}-\w{3}-\d{4})", 
#                     text
#                 )
#             if discharge_match:
#                 extracted_data["Date of Discharge"] = discharge_match.group(1)

#     except Exception as e:
#         print(f"Error processing PDF: {str(e)}", file=sys.stderr)

#     return extracted_data

# if __name__ == "__main__":
#     if len(sys.argv) != 2:
#         print("Usage: python script.py <path_to_pdf>")
#         sys.exit(1)

#     result = extract_info_from_pdf(sys.argv[1])
#     print(json.dumps(result, indent=4))

import pdfplumber
import re
import json
import sys

def suppress_warnings():
    import warnings
    warnings.filterwarnings("ignore", message="CropBox missing from /Page, defaulting to MediaBox")

def extract_info_from_pdf(pdf_path):
    suppress_warnings()
    
    extracted_data = {
        "Name of the Patient": "null",
        "Policy No": "null",
        "Policy Period": "null",
        "Date of Admission": "null",
        "Date of Discharge": "null"
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()

            # Improved Patient Name extraction to handle multi-line names
            # Look for "Patient Name" followed by any text until "Age"
            patient_match = re.search(
                r"Patient\s*Name\s*:\s*([\s\S]+?)\s*Age\s*:", 
                text
            )
            if patient_match:
                # Clean up the name - remove extra spaces and newlines
                name = ' '.join(patient_match.group(1).strip().split())
                extracted_data["Name of the Patient"] = name

            # Policy Number
            policy_match = re.search(r"Policy\s*No\s*:\s*([A-Z0-9]+)", text)
            if policy_match:
                extracted_data["Policy No"] = policy_match.group(1).strip()

            # Policy Period
            period_match = re.search(
                r"Policy\s*period\s*:\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})", 
                text
            )
            if period_match:
                extracted_data["Policy Period"] = f"{period_match.group(1)} To {period_match.group(2)}"

            # Date of Admission
            admission_match = re.search(
                r"Expected\s*Date\s*of\s*Admission\s*:\s*(\d{2}-\w{3}-\d{4})", 
                text
            )
            if not admission_match:
                admission_match = re.search(
                    r"Expected\s*Date\s*of\s*Admission\s*:\s*\n\s*(\d{2}-\w{3}-\d{4})", 
                    text
                )
            if admission_match:
                extracted_data["Date of Admission"] = admission_match.group(1)

            # Date of Discharge
            discharge_match = re.search(
                r"Expected\s*Date\s*of\s*Discharge\s*:\s*(\d{2}-\w{3}-\d{4})", 
                text
            )
            if not discharge_match:
                discharge_match = re.search(
                    r"Expected\s*Date\s*of\s*Discharge\s*:\s*\n\s*(\d{2}-\w{3}-\d{4})", 
                    text
                )
            if discharge_match:
                extracted_data["Date of Discharge"] = discharge_match.group(1)

    except Exception as e:
        print(f"Error processing PDF: {str(e)}", file=sys.stderr)

    return extracted_data

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_pdf>")
        sys.exit(1)

    result = extract_info_from_pdf(sys.argv[1])
    print(json.dumps(result, indent=4))