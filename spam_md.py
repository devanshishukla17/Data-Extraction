import re
import json
from typing import Dict, Optional

def extract_medical_authorization_data(text: str) -> Dict[str, str]:
    """
    Extract medical authorization data from MD India PDF text
    """
    
    # Initialize result dictionary with null values
    result = {
        "AL Number": "null",
        "Approved Amount": "null", 
        "Date & Time": "null",
        "Date of Admission": "null",
        "Date of Discharge": "null",
        "Hospital Address": "null",
        "Letter Type": "null",
        "Name of the Patient": "null",
        "Policy No": "null",
        "Policy Period": "null",
        "Remarks": "null",
        "Total Bill Amount": "null",
        "UHID Number": "null"
    }
    
    # Extract AL Number (Claim Number)
    claim_match = re.search(r'Claim Number\s*:\s*([A-Z0-9]+)', text)
    if claim_match:
        result["AL Number"] = claim_match.group(1)
    
    # Extract Approved Amount (Total Authorized Amount)
    approved_match = re.search(r'Total Authorized Amount.*?Rs\.\s*([0-9,]+)', text, re.DOTALL)
    if approved_match:
        result["Approved Amount"] = approved_match.group(1).replace(',', '')
    
    # Extract Date & Time (from last enhancement)
    date_time_matches = re.findall(r'ENHANCEMENT.*?(\d{2}/\d{2}/\d{4})\s+[A-Z0-9]+\s+(\d{1,2}:\d{2}:\d{2}[AP]M)', text)
    if date_time_matches:
        last_date, last_time = date_time_matches[-1]
        result["Date & Time"] = f"{last_date} {last_time}"
    
    # Extract Date of Admission
    admission_match = re.search(r'Expected Date of Admission\s*:\s*(\d{2}/\d{2}/\d{4})', text)
    if admission_match:
        result["Date of Admission"] = admission_match.group(1)
    
    # Extract Date of Discharge
    discharge_match = re.search(r'Expected Date of Discharge\s*:\s*(\d{2}/\d{2}/\d{4})', text)
    if discharge_match:
        result["Date of Discharge"] = discharge_match.group(1)
    
    # Extract Hospital Address
    hospital_match = re.search(r'IC Name\s*:\s*([^\n]+)', text)
    hospital_addr_match = re.search(r'IC Name\s*:.*?\n([^\n]+)\n([^\n]+)', text, re.DOTALL)
    if hospital_match and hospital_addr_match:
        hospital_name = hospital_match.group(1).strip()
        address_line = hospital_addr_match.group(2).strip()
        result["Hospital Address"] = f"hospital name: {hospital_name}\naddress: {address_line}"
    
    # Extract Letter Type (check for Enhancement/Initial/Approval)
    if "ENHANCEMENT" in text:
        result["Letter Type"] = "Enhancement"
    elif "INITIAL" in text:
        result["Letter Type"] = "Initial"
    else:
        result["Letter Type"] = "Approval"
    
    # Extract Patient Name
    patient_match = re.search(r'Patient Name\s*:\s*([^\n]+)', text)
    if patient_match:
        result["Name of the Patient"] = patient_match.group(1).strip()
    
    # Extract Policy Number
    policy_match = re.search(r'Policy Number\s*:\s*([^\n]+)', text)
    if policy_match:
        result["Policy No"] = policy_match.group(1).strip()
    
    # Extract Policy Period
    period_match = re.search(r'Policy Period\s*:\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})', text)
    if period_match:
        result["Policy Period"] = f"{period_match.group(1)} to {period_match.group(2)}"
    
    # Extract Remarks (Authorization Remarks section)
    remarks_match = re.search(r'Authorisation Remarks\s*:(.*?)(?=Hospital Agreed Tariff|Terms and Conditions)', text, re.DOTALL)
    if remarks_match:
        remarks_text = remarks_match.group(1).strip()
        # Clean up the remarks text
        remarks_text = re.sub(r'\s+', ' ', remarks_text)
        result["Remarks"] = remarks_text
    
    # Extract Total Bill Amount
    bill_match = re.search(r'Total Bill Amount\s*:\s*([0-9,]+)', text)
    if bill_match:
        result["Total Bill Amount"] = f"Rs. {bill_match.group(1)}.00"
    
    # Extract UHID Number (Rohini ID)
    uhid_match = re.search(r'Rohini ID\s*:\s*([0-9]+)', text)
    if uhid_match:
        result["UHID Number"] = uhid_match.group(1)
    
    return result

def process_pdf_text(pdf_text: str) -> str:
    """
    Process PDF text and return extracted data as JSON string
    """
    extracted_data = extract_medical_authorization_data(pdf_text)
    return json.dumps(extracted_data, indent=4)

# Example usage:
if __name__ == "__main__":
    # Your PDF text would go here
    pdf_content = """
    [Your PDF text content here]
    """
    
    # Extract data
    result = extract_medical_authorization_data(pdf_content)
    
    # Print as formatted JSON
    print(json.dumps(result, indent=4))
    
    # Or save to file
    with open('extracted_data.json', 'w') as f:
        json.dump(result, f, indent=4)

# Additional utility functions for PDF processing
def extract_from_multiple_pdfs(pdf_texts: list) -> list:
    """
    Extract data from multiple PDF texts
    """
    results = []
    for i, text in enumerate(pdf_texts):
        try:
            data = extract_medical_authorization_data(text)
            data['source_file'] = f"pdf_{i+1}"
            results.append(data)
        except Exception as e:
            print(f"Error processing PDF {i+1}: {str(e)}")
    return results

def validate_extracted_data(data: dict) -> dict:
    """
    Validate and clean extracted data
    """
    # Remove 'null' strings and replace with actual None
    for key, value in data.items():
        if value == "null" or value == "":
            data[key] = None
    
    # Validate date formats
    date_fields = ["Date of Admission", "Date of Discharge"]
    for field in date_fields:
        if data.get(field) and not re.match(r'\d{2}/\d{2}/\d{4}', data[field]):
            print(f"Warning: Invalid date format in {field}: {data[field]}")
    
    return data

