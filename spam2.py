import pdfplumber
import re
import sys
import json

def extract_address(text):
    if "To," in text and "Policy No" in text:
        start_idx = text.find("To,")
        end_idx = text.find("Phone")
        address_block = text[start_idx:end_idx]
        
        # Find the hospital name (assuming it's before the address lines)
        hospital_name = None
        for line in address_block.split('\n'):
            if "Apollo" in line and "Hospitals" in line:
                hospital_name = line.strip()
                break
        
        # Find the address line starting with #
        address_lines = []
        for line in address_block.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                # Extract just the address portion
                address = line.split('#')[-1].strip()
                # Remove any trailing field labels
                address = re.sub(r'\b(?:CCN|MDI|Patient|Policy)\b.*', '', address)
                address_lines.append(address)
            elif address_lines and not any(x in line for x in [':', 'CCN', 'MDI']):
                # Continue address if it's part of the same block
                address_lines.append(line)
        
        if address_lines:
            # Join and clean the address
            full_address = ' '.join(' '.join(address_lines).split())
            address_part = full_address.split('Phone')[0].strip()
            
            # Combine hospital name with address if found
            if hospital_name:
                return f"{hospital_name}: {address_part}"
            return address_part
    
    return None

def extract_reasons(text):
    # Find the table section
    start_marker = "we desired the following information at the earliest to process the RAL further:"
    end_marker = "Thanking You"
    
    if start_marker in text and end_marker in text:
        table_section = text.split(start_marker)[1].split(end_marker)[0]
        # Extract all lines that are part of the table content
        reasons = []
        for line in table_section.split('\n'):
            line = line.strip()
            if line and not line.startswith('|') and not line.startswith('Sr.No.'):
                reasons.append(line)
        # Join with newlines and clean up extra spaces
        return '\n'.join(reasons).strip()
    return None

def extract_info_from_pdf(pdf_path):
    extracted_data = {
        "Name of the Patient": "null",
        "Policy No": "null",
        "Hospital Address": "null",
        "CCN": "null",
        "Letter Type": "Request",
        "MDI ID No": "null",
        "Reason": "null"
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            
            # Extract Patient Name
            patient_match = re.search(r"Patient Name\s*:\s*([^\n]+)", text)
            if patient_match:
                extracted_data["Name of the Patient"] = patient_match.group(1).strip().split('\n')[0]
            
            # Extract Policy No
            if "Policy No :" in text:
                extracted_data["Policy No"] = text.split("Policy No :")[1].split()[0].strip()
            
            # Extract MDI ID No
            if "MDI ID No :" in text:
                extracted_data["MDI ID No"] = text.split("MDI ID No :")[1].split()[0].strip()
            
            # Extract CCN
            if "CCN :" in text:
                extracted_data["CCN"] = text.split("CCN :")[1].split()[0].strip()
            
            # Extract address
            address = extract_address(text)
            if address:
                extracted_data["Hospital Address"] = address
            
            # Extract reasons from the table
            reasons = extract_reasons(text)
            if reasons:
                extracted_data["Reason"] = reasons
    
    except Exception as e:
        print(f"Warning: {str(e)}", file=sys.stderr)
    
    return extracted_data

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python spam.py <path_to_pdf>")
        sys.exit(1)
    
    try:
        result = extract_info_from_pdf(sys.argv[1])
        print(json.dumps(result, indent=4))
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)