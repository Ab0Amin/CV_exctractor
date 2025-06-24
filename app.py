import streamlit as st
import pdfplumber
import pandas as pd
import io
import json
from google import genai
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# System prompt for Gemini
system_prompt = """
You are a resume parser. Extract structured data from any CV text and return valid JSON that maps to the following schema.

Include only fields that can be extracted directly from the CV. Omit any system-generated fields like IDs.

Map links like LinkedIn, GitHub, and Portfolio to their correct fields. If the text includes a label (e.g., “LinkedIn:”) followed by a non-clickable name, but embedded links are listed below under [Resolved Links], use the actual URLs.

Return all dates in YYYY-MM-DD format, and normalize phone numbers to international format (e.g., +[CountryCode]-[Number]).

Return ONLY valid JSON. Do not include explanation or markdown. Start with '{' and end with '}'.


ERD:
 
	1.	Candidate
	•	CandidateID (Primary Key)
	•	FullName
	•	Nationality
	•	CurrentLocation
	•	Phone
	•	Email
	•	LinkedInURL
	•	CareerSummary
	•	ProfilePhoto (Base64 encoded string)
	•	PortfolioLink
	2.	EmploymentHistory
	•	EmploymentID (Primary Key)
	•	CandidateID (Foreign Key)
	•	JobTitle
	•	Company
	•	Location
	•	StartDate
	•	EndDate
	•	Responsibilities
	3.	Education
	•	EducationID (Primary Key)
	•	CandidateID (Foreign Key)
	•	Degree
	•	Institution
	•	Location
	•	GraduationDate
	•	Major
	4.	Certifications
	•	CertificationID (Primary Key)
	•	CandidateID (Foreign Key)
	•	CertificationTitle
	•	IssuingOrganization
	•	IssueDate
	•	ExpiryDate
	5.	Skills
	•	SkillID (Primary Key)
	•	CandidateID (Foreign Key)
	•	SkillName
	•	ProficiencyLevel (e.g., Beginner, Intermediate, Advanced)
	6.	Projects
	•	ProjectID (Primary Key)
	•	CandidateID (Foreign Key)
	•	ProjectTitle
	•	ProjectDescription
	•	Role
	•	Duration
	•	TechnologiesUsed
	7.	Publications
	•	PublicationID (Primary Key)
	•	CandidateID (Foreign Key)
	•	PublicationTitle
	•	PublicationDate
	•	Publisher
	•	Description
	8.	VolunteerExperience
	•	VolunteerID (Primary Key)
	•	CandidateID (Foreign Key)
	•	Organization
	•	Role
	•	Duration
	•	ActivitiesImpact
	9.	References
	•	ReferenceID (Primary Key)
	•	CandidateID (Foreign Key)
	•	ReferenceName
	•	Position
	•	ContactInformation
	•	RelationToCandidate
	10.	OtherInformation
 
	•	OtherInfoID (Primary Key)
	•	CandidateID (Foreign Key)
	•	InformationType (e.g., hobbies, languages, portfolio link)
	•	Details
 
	11.	Languages
 
	•	LanguageID (Primary Key)
	•	CandidateID (Foreign Key)
	•	LanguageName
	•	ProficiencyLevel (e.g., Native, Fluent, Intermediate, Beginner)
 
	12.	Awards
 
	•	AwardID (Primary Key)
	•	CandidateID (Foreign Key)
	•	AwardTitle
	•	IssuingOrganization
	•	AwardDate
	•	Description
 
	13.	Interests
 
	•	InterestID (Primary Key)
	•	CandidateID (Foreign Key)
	•	InterestName
	•	Description
"""

st.title("📄 CV Parser - Kafaat solution")
uploaded_files = st.file_uploader("Upload one or more CVs (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files and st.button("Parse CVs"):
    excel_buffer = io.BytesIO()
    writer = pd.ExcelWriter(excel_buffer, engine="openpyxl")

    preview_rows = []
    with st.spinner("🔄 Processing CVs... Please wait"):
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

                # تنسيق الشيت مباشرة من writer.book
                ws = writer.book[candidate_name[:31]]

                fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
                bold = Font(bold=True)

                section = None
                for row in range(2, ws.max_row + 1):
                    cell = ws[f"A{row}"]
                    if cell.value and cell.value != section:
                        section = cell.value
                        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
                        cell.fill = fill
                        cell.font = bold
                        ws[f"B{row}"] = None
                        ws[f"C{row}"] = None

                excel_buffer.seek(0)
                wb.save(excel_buffer)
                excel_buffer.seek(0)

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
