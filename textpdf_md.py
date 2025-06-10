import PyPDF2
import re
from pprint import pprint

def extract_pdf_data(pdf_path):
    # Initialize a PDF reader object
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        # Extract text from all pages with better line handling
        for page in reader.pages:
            text += page.extract_text() + "\n"  # Add newline between pages

    # Initialize data dictionary with None values
    data = {key: None for key in [
        "AL Number", "Approved Amount", "Date & Time",
        "Date of Admission", "Date of Discharge", "Hospital Address",
        "Letter Type", "Name of the Patient", "Policy No",
        "Policy Period", "Remarks", "Total Bill Amount", "UHID Number"
    ]}
    data["Letter Type"] = "Approval"
    data["UHID Number"] = "Not explicitly mentioned in the document"

    # Improved field extraction with more specific patterns
    try:
        # AL Number (Claim Number)
        al_match = re.search(r'Claim Number\s*:\s*(\w+)', text)
        if al_match:
            data["AL Number"] = al_match.group(1).strip()

        # Approved Amount
        amount_match = re.search(r'Total Authorized Amount:\s*Rs\. ([\d,]+)', text, re.IGNORECASE)
        if not amount_match:
            amount_match = re.search(r'Total Authorized Amount:\s*[\w\s]+Only\.\s*\(Rs\. ([\d,]+)\)', text)
        if amount_match:
            data["Approved Amount"] = f"Rs. {amount_match.group(1)}"

        # Date & Time
        date_times = re.findall(r'(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2}[AP]M)', text)
        if date_times:
            data["Date & Time"] = [f"{dt[0]} {dt[1]}" for dt in date_times]

        # Admission/Discharge Dates
        adm_match = re.search(r'Expected Date of Admission\s*:\s*(\d{2}/\d{2}/\d{4})', text)
        dis_match = re.search(r'Expected Date of Discharge\s*:\s*(\d{2}/\d{2}/\d{4})', text)
        if adm_match:
            data["Date of Admission"] = adm_match.group(1)
        if dis_match:
            data["Date of Discharge"] = dis_match.group(1)

        # Hospital Address
        hospital_match = re.search(r'To,\s*The Medical Director,\s*([^\n]+)\s*Near\s*([^\n]+)', text)
        if hospital_match:
            data["Hospital Address"] = f"{hospital_match.group(1).strip()}, Near {hospital_match.group(2).strip()}"

        # Patient Name
        patient_match = re.search(r'Patient Name\s*[|:]\s*([^\n|]+)', text)
        if patient_match:
            data["Name of the Patient"] = patient_match.group(1).strip()

        # Policy Number
        policy_match = re.search(r'Policy Number\s*[|:]\s*([^\n|]+)', text)
        if policy_match:
            data["Policy No"] = policy_match.group(1).strip()

        # Policy Period
        period_match = re.search(r'Policy Period\s*[|:]\s*([^\n|]+)', text)
        if period_match:
            data["Policy Period"] = period_match.group(1).strip()

        # Remarks
        remarks_start = text.find("Authorisation Remarks :")
        if remarks_start > 0:
            remarks_end = text.find("Head Office:", remarks_start)
            if remarks_end > remarks_start:
                remarks = text[remarks_start:remarks_end].replace("Authorisation Remarks :", "").strip()
                data["Remarks"] = " ".join(remarks.split())  # Normalize whitespace

        # Total Bill Amount
        bill_match = re.search(r'Total Bill Amount\s*:\s*([\d,]+)', text)
        if bill_match:
            data["Total Bill Amount"] = f"Rs. {bill_match.group(1)}"

    except Exception as e:
        print(f"Error during extraction: {str(e)}")

    return data

pdf_path = "C:\\Desktop\\INTERNSHIP\\extraction\\PDFs\\mdindia\\MD INDIA Enhancement Approved.pdf"
extracted_data = extract_pdf_data(pdf_path)
pprint(extracted_data)