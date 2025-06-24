import pdfplumber
import re
import json
import sys

def extract_info_from_pdf(pdf_path):
    data = {
        "AL Number": "null",
        "Name of the Patient": "null",
        "Policy No": "null",
        "Policy Period": "null",
        "Hospital Address": "null",
        "Rohini ID": "null",
        "Letter Type": "null",
        "Date of Admission": "null",
        "Date of Discharge": "null",
        "Authorization Details": {
            "Date and Time": {},
            "Authorized Amount": 0
        },
        "Approved Amount": 0,
        "Remarks": "null"
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])

            # Clean up text
            text = re.sub(r'\s+', ' ', text)

            # AL Number
            m = re.search(r"Claim Number AL[: ]+(\d+)", text)
            if m:
                data["AL Number"] = m.group(1)

            # Name of the Patient (supports multiline name)
            m = re.search(r"Patient Name\s*:\s*([A-Z ]+?) Age :", text)
            if m:
                data["Name of the Patient"] = m.group(1).strip()

            # Policy No
            m = re.search(r"Policy No\s*:\s*(\d+)", text)
            if m:
                data["Policy No"] = m.group(1)

            # Policy Period
            m = re.search(r"Policy period\s*:\s*(\d{2}-\d{2}-\d{4}) to (\d{2}-\d{2}-\d{4})", text, re.IGNORECASE)
            if m:
                data["Policy Period"] = f"{m.group(1)} to {m.group(2)}"

            # Hospital Address
            m = re.search(r"(MANIPAL HOSPITAL.*?) Name of Insurance Company", text)
            if m:
                data["Hospital Address"] = m.group(1).strip()

            # Rohini ID
            m = re.search(r"Rohini ID\s*:\s*(\d+)", text)
            if m:
                data["Rohini ID"] = m.group(1)

            # Letter Type
            if "Cashless Authorization Letter" in text:
                data["Letter Type"] = "Approval"

            # Date of Admission
            m = re.search(r"Expected Date of Admission\s*:\s*([0-9]{2}-[A-Za-z]+-[0-9]{4})", text)
            if m:
                data["Date of Admission"] = m.group(1)

            # Date of Discharge
            m = re.search(r"Expected Date of Discharge\s*:\s*([0-9]{2}-[A-Za-z]+-[0-9]{4})", text)
            if m:
                data["Date of Discharge"] = m.group(1)

            # Authorization Details block
            m = re.search(
                r"Authorization Details:.*?(\d{2}/[A-Za-z]+/\d{4})\s+(\d{2}:\d{2}:\d{2})\s+([0-9\-]+)\s+([\d,]+\.\d+)\s+(Cashless Approved)",
                text
            )
            if m:
                date_time = f"{m.group(1)} {m.group(2)}"
                approved_amt = int(float(m.group(4).replace(',', '')))
                data["Authorization Details"]["Date and Time"][date_time] = m.group(5)
                data["Authorization Details"]["Authorized Amount"] = approved_amt

            # Approved Amount (final)
            m = re.search(r"Total Approved amount Rs\.?\s*([0-9,]+)", text)
            if m:
                data["Approved Amount"] = int(m.group(1).replace(',', ''))

            # Remarks
            m = re.search(r"Authorization remarks\s*:\s*(.*?) Hospital Agreed", text)
            if m:
                data["Remarks"] = m.group(1).strip()

    except Exception as e:
        print(f"Error during PDF processing: {e}", file=sys.stderr)

    return data

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_pdf>")
        sys.exit(1)

    result = extract_info_from_pdf(sys.argv[1])
    print(json.dumps(result, indent=4))
