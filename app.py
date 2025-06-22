import streamlit as st
import pdfplumber
import pandas as pd
import io
from google import genai
import json


# Set Gemini API key

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# System prompt for Gemini
system_prompt = """
You are a resume parser. Extract structured data from any CV text and return valid JSON that maps to the following schema.

Include only fields that can be extracted directly from the CV. Omit any system-generated fields like IDs.

Map links like LinkedIn, GitHub, and Portfolio to their correct fields. If the text includes a label (e.g., “LinkedIn:”) followed by a non-clickable name, but embedded links are listed below under [Resolved Links], use the actual URLs.

Return all dates in YYYY-MM-DD format, and normalize phone numbers to international format (e.g., +[CountryCode]-[Number]).

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
    results = []

    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            text_lines = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_lines.append(page_text)
                for link in page.hyperlinks:
                    uri = link.get("uri", "")
                    if uri:
                        text_lines.append(f"Embedded Link: {uri}")

            text = "\n".join(text_lines)

        # Compose input content
        full_prompt = system_prompt + "\n\nCV Content:\n" + text

        # response = genai.generate_text(
        response = client.models.generate_content(
           
       
         model="gemini-1.5-flash",
    config={
        "response_mime_type": "application/json",
    },
            contents=full_prompt,

        )

        try:
            parsed = json.loads(response.text)
            candidate = parsed.get("Candidate", {})
            skills = ", ".join(s.get("SkillName", "") for s in parsed.get("Skills", []))


            flat = {"File": file.name}
            print("flat",flat)
            for key, value in parsed.items():
                flat[key] = json.dumps(value, ensure_ascii=False)

            results.append(flat)
            print("results", results)
            # results.append({
            #     "File": file.name,
            #     "FullName": candidate.get("FullName", ""),
            #     "Email": candidate.get("Email", ""),
            #     "Phone": candidate.get("Phone", ""),
            #     "LinkedIn": candidate.get("LinkedInURL", ""),
            #     "Portfolio": candidate.get("PortfolioLink", ""),
            #     "Location": candidate.get("CurrentLocation", ""),
            #     "Skills": skills
            # })
        except Exception as e:
            st.error(f"Failed to parse {file.name}: {e} \nResponse: {flat}")

    df = pd.DataFrame(results)
    st.dataframe(df)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)

    st.download_button(
        label="📥 Download Results as Excel",
        data=buffer,
        file_name="parsed_cvs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
