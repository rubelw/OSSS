#!/usr/bin/env python3

import pdfplumber

pdf_path = "iowa_district_codes.pdf"
output_text_file = "iowa_district_codes.txt"

all_text = []

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text.append(text)

# Save to a text file
with open(output_text_file, "w", encoding="utf-8") as f:
    f.write("\n".join(all_text))

print(f"Extracted text saved to {output_text_file}")
