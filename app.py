import streamlit as st
import pdfplumber
import pandas as pd
import io
import json
from google import genai

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# System prompt for Gemini
system_prompt = """
You are a resume parser. Extract structured data from any CV text and return valid JSON that maps to the following schema.

Include only fields that can be extracted directly from the CV. Omit any system-generated fields like IDs.

Map links like LinkedIn, GitHub, and Portfolio to their correct fields. If the text includes a label (e.g., “LinkedIn:”) followed by a non-clickable name, but embedded links are listed below under [Resolved Links], use the actual URLs.

Return all dates in YYYY-MM-DD format, and normalize phone numbers to international format (e.g., +[CountryCode]-[Number]).

Return ONLY valid JSON. Do not include explanation or markdown. Start with '{' and end with '}'.

Expected JSON structure:
{
  "Candidate": {
    "FullName",
    "Nationality",
    "CurrentLocation",
    "Phone",
    "Email",
    "LinkedInURL",
    "CareerSummary",
    "ProfilePhoto",
    "PortfolioLink"
  },
  "EmploymentHistory": [ ... ],
  "Education": [ ... ],
  "Certifications": [ ... ],
  "Skills": [ ... ],
  "Projects": [ ... ],
  "Publications": [ ... ],
  "VolunteerExperience": [ ... ],
  "References": [ ... ],
  "OtherInformation": [ ... ],
  "Languages": [ ... ],
  "Awards": [ ... ],
  "Interests": [ ... ]
}
"""

st.title("📄 CV Parser - Gemini Powered")
uploaded_files = st.file_uploader("Upload one or more CVs (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files and st.button("Parse CVs"):
    excel_buffer = io.BytesIO()
    writer = pd.ExcelWriter(excel_buffer, engine="openpyxl")

    preview_rows = []

    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            text_lines = []
            for page in pdf.pages:
                text_lines.append(page.extract_text() or "")
                for link in page.hyperlinks:
                    uri = link.get("uri", "")
                    if uri:
                        text_lines.append(f"Embedded Link: {uri}")
        text = "\n".join(text_lines)

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            config={"response_mime_type": "application/json"},
            contents=system_prompt + "\n\nCV Content:\n" + text,
        )

        try:
            parsed = json.loads(response.text.strip())
            candidate_name = parsed.get("Candidate", {}).get("FullName", "Unknown").strip().replace(" ", "_")

            # Build table-like structure
            flat_rows = []
            for section, content in parsed.items():
                if isinstance(content, dict):
                    for k, v in content.items():
                        flat_rows.append({"Section": section, "Field": k, "Value": v})
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                flat_rows.append({"Section": section, "Field": k, "Value": v})
                            flat_rows.append({"Section": "", "Field": "", "Value": ""})  # spacer
                        else:
                            flat_rows.append({"Section": section, "Field": "", "Value": item})
                else:
                    flat_rows.append({"Section": section, "Field": "", "Value": content})

            df_flat = pd.DataFrame(flat_rows)
            df_flat.to_excel(writer, sheet_name=candidate_name[:31], index=False)

            preview_rows.append({
                "File": file.name,
                "Candidate": parsed.get("Candidate", {}).get("FullName", "")
            })

        except Exception as e:
            st.error(f"❌ Failed to parse {file.name}: {e}")
            st.code(response.text)

    # Preview summary
    if preview_rows:
        st.dataframe(pd.DataFrame(preview_rows))

    writer.close()
    excel_buffer.seek(0)

    st.download_button(
        label="📥 Download Organized Excel",
        data=excel_buffer,
        file_name="organized_cv_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
