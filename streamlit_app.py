#streamlit run streamlit_app.py
#in terminal
import streamlit as st
import pandas as pd
import re
import csv
from io import StringIO

st.title("Evening Batch Routine Generator")

st.write("This app generates a timetable for courses based on faculty and course data from Google Sheets.")

# Inputs
google_sheet_url_courses = st.text_input("Enter Google Sheet URL for Courses:", "https://docs.google.com/spreadsheets/d/1FaY1YLTtfoA7Rb2SlQXyYx5GljvKsp6b_UdLzxugJnM/edit?gid=0#gid=0")
google_sheet_url_faculty = st.text_input("Enter Google Sheet URL for Faculty:", "https://docs.google.com/spreadsheets/d/1FaY1YLTtfoA7Rb2SlQXyYx5GljvKsp6b_UdLzxugJnM/edit?gid=402428488#gid=402428488")

batches_input = st.text_input("Enter batches (comma-separated):", "232,233,241,242,243,251,252,253,261,262")
batches = [b.strip() for b in batches_input.split(',')]

# Teacher availability
st.subheader("Teacher Availability")
st.write("Edit the available slots for each teacher. Select the slots they can teach.")

default_availability = {
    "DSMA": ["Fri_3", "Fri_4"],
    "SB": ["Fri_5"],
    "NNR": ["Fri_6", "Fri_7"],
    "MRS": ["Fri_1", "Fri_2", "Fri_5", "Fri_6"],
    "TI": ["Fri_2", "Fri_3", "Fri_5", "Fri_7"],
    "MAG": ["Fri_4", "Fri_5", "Fri_7", "Fri_8"],
    "MFH": ["Fri_1", "Fri_2", "Fri_3", "Fri_4" ],
    "SI": ["Fri_2", "Fri_3", "Fri_5", "Fri_6"],
    "MRM": ["Fri_1","Fri_2", "Fri_4", "Fri_5", "Fri_6"]
}

availability_presets = {}
for teacher in default_availability.keys():
    options = [f"Fri_{i}" for i in range(1,9)]
    default_avail = default_availability[teacher]
    selected = st.multiselect(f"Available slots for {teacher}", options, default=default_avail, key=teacher)
    availability_presets[teacher] = selected

# Load courses to extract semesters
try:
    sheet_id = google_sheet_url_courses.split('/d/')[1].split('/edit')[0]
    csv_export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    df_courses = pd.read_csv(csv_export_url)
    
    # Extract semesters
    semesters = set()
    for col in df_courses.columns:
        if re.match(r'^\d{3}', col):
            for val in df_courses[col].dropna():
                val_str = str(val).strip()
                matches = re.findall(r'(?:Summer|Fall|Spring|Winter)\d{4}', val_str)
                semesters.update(matches)
    
    all_semesters = sorted(list(semesters), reverse=True)
    if not all_semesters:
        st.error("No semesters found in the courses sheet.")
        st.stop()
    
    selected_semester = st.selectbox("Select Semester:", all_semesters, index=0)
    
except Exception as e:
    st.error(f"Error loading courses sheet: {str(e)}")
    st.stop()

if st.button("Generate Timetable"):
    try:
        # Process courses
        sheet_id = google_sheet_url_courses.split('/d/')[1].split('/edit')[0]
        csv_export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df_from_google_sheet = df_courses
        csv_file = "/tmp/courses.csv"
        df_from_google_sheet.to_csv(csv_file, index=False)

        semester_courses = {batch: [] for batch in batches}
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                course_code = row["Course Code"]
                course_name = row["Course Name"]
                for column_header, cell_value in row.items():
                    match = re.match(r"^(\d{3})", column_header)
                    if match:
                        extracted_batch = match.group(1)
                        if extracted_batch in batches and selected_semester in cell_value:
                            semester_courses[extracted_batch].append(f"{course_code} — {course_name}")

        # Process faculty
        sheet_id_faculty = google_sheet_url_faculty.split('/d/')[1].split('/edit')[0]
        gid_match = re.search(r'gid=(\d+)', google_sheet_url_faculty)
        gid_faculty = gid_match.group(1) if gid_match else "0"
        csv_export_url_faculty = f"https://docs.google.com/spreadsheets/d/{sheet_id_faculty}/export?format=csv&gid={gid_faculty}"
        df_raw_online = pd.read_csv(csv_export_url_faculty, header=None)

        header_row_index = -1
        for r_idx in range(min(df_raw_online.shape[0], 20)):
            if df_raw_online.shape[1] > 0 and pd.notna(df_raw_online.iloc[r_idx, 0]) and isinstance(df_raw_online.iloc[r_idx, 0], str) and df_raw_online.iloc[r_idx, 0].strip().lower() == 'initial':
                header_row_index = r_idx
                break
        if header_row_index == -1:
            st.error("Could not find header row with 'Initial'.")
            st.stop()

        new_header = df_raw_online.iloc[header_row_index, 0:8]
        df_from_google_sheet_faculty = df_raw_online.iloc[header_row_index + 1:32, 0:8].copy()
        df_from_google_sheet_faculty.columns = new_header.str.strip()
        df_from_google_sheet_faculty = df_from_google_sheet_faculty.rename(columns={'Course Code': 'CourseCode'})
        csv_file_faculty = "/tmp/faculty.csv"
        df_from_google_sheet_faculty.to_csv(csv_file_faculty, index=False)

        # Extract faculty data function
        def extract_faculty_data(file_path):
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip()
            df['Initial'] = df['Initial'].ffill()
            def get_section(row):
                title = str(row.get('Course Name', ''))
                extra = str(row.get('Section', ''))
                sec_match = re.search(r'\(sec-(\d+)\)', title, re.IGNORECASE)
                if sec_match:
                    return f"Section {sec_match.group(1)}"
                if extra.lower() in ['2', '3']:
                    return extra.capitalize()
                return "N/A"
            df['Section'] = df.apply(get_section, axis=1)
            required_cols = ['Initial', 'CourseCode', 'Course Name','Credit', 'Section']
            existing_required_cols = [col for col in required_cols if col in df.columns]
            result = df[existing_required_cols].dropna(subset=['CourseCode'])
            course_codes_to_exclude = ['TE-409', 'TE-410', 'TE-411']
            result = result[~result['CourseCode'].isin(course_codes_to_exclude)]
            return result

        final_df = extract_faculty_data(csv_file_faculty)

        # Combine data
        summer_courses_list = []
        for batch, courses in semester_courses.items():
            for course_str in courses:
                parts = course_str.split(' — ', 1)
                course_code = parts[0].strip()
                course_name = parts[1].strip() if len(parts) > 1 else course_code
                normalized_course_code = course_code.replace(' ', '-').upper()
                summer_courses_list.append({"Batch": batch, "Course Code": normalized_course_code, "Course Name": course_name})

        df_summer_courses = pd.DataFrame(summer_courses_list)
        df_faculty = final_df.copy()
        df_faculty['CourseCode'] = df_faculty['CourseCode'].astype(str).str.replace(' ', '-').str.upper()
        df_faculty = df_faculty.rename(columns={"CourseCode": "Course Code"})
        combined_df = pd.merge(df_summer_courses, df_faculty, on="Course Code", how="inner", suffixes=('_x', '_y'))
        combined_df = combined_df[["Batch", "Course Name_x", "Course Code", "Initial","Section","Credit"]]
        combined_df = combined_df.rename(columns={"Course Name_x": "Course Name"})
        combined_df = combined_df.sort_values(by=['Batch', 'Course Code'], ascending=[False, True]).reset_index(drop=True)

        # Timetable generation
        DAYS = ["Fri"]
        SLOTS = [1, 2, 3, 4, 5, 6, 7, 8]
        TIME_MAP = {1: "9 am to 10 am", 2: "10 am to 11 am", 3: "11 am to 12 pm", 4: "12 pm to 1 pm", 5: "2 pm to 3 pm", 6: "3 pm to 4 pm", 7: "4 pm to 5 pm", 8: "5 pm to 6 pm"}
        timeslots = [f"{d}_{s}" for d in DAYS for s in SLOTS]

        df = combined_df
        grouped = df.groupby(['Course Code', 'Section', 'Initial']).agg({'Batch': lambda x: sorted(list(x.unique())), 'Course Name': 'first', 'Credit': 'first'}).reset_index()

        faculties = {}
        for initial in df['Initial'].unique():
            faculties[initial] = {"name": initial, "availability": availability_presets.get(initial, timeslots)}

        sessions = []
        fixed_eng102_session = None
        for _, row in grouped.iterrows():
            session_item = {
                "name": row['Course Code'],
                "faculty": row['Initial'],
                "batches": row['Batch'],
                "section": row['Section'],
                "course_name": row['Course Name'],
                "credit": row['Credit'],
                "hours": 1
            }
            if session_item['name'] == 'ENG-102' and session_item['faculty'] == 'SB':
                fixed_eng102_session = session_item
            else:
                sessions.append(session_item)

        rooms = [f"R{i}" for i in range(1, 5)]
        all_rooms_for_display = [f"R{i}" for i in range(1, 6)]

        timetable = {}

        def can_assign(slot, room, session, timetable):
            if slot not in timetable:
                return True
            SPLIT_COURSES = ["TE-401", "TE-406", "TE-313"]
            for entry in timetable[slot]:
                if entry["faculty"] == session["faculty"]:
                    return False
                if entry["room"] == room:
                    return False
                for b in session["batches"]:
                    if b in entry["batches"]:
                        if session["name"] in SPLIT_COURSES and entry["subject"] == session["name"]:
                            continue
                        else:
                            return False
            return True

        def assign_session(index):
            if index == len(sessions): return True
            session = sessions[index]
            for slot in faculties[session["faculty"]]["availability"]:
                for room in rooms:
                    if can_assign(slot, room, session, timetable):
                        timetable.setdefault(slot, []).append({
                            "subject": session["name"],
                            "faculty": session["faculty"],
                            "batches": session["batches"],
                            "room": room,
                            "course_name": session["course_name"],
                            "section": session["section"],
                            "credit": session["credit"]
                        })
                        if assign_session(index + 1): return True
                        timetable[slot].pop()
                        if not timetable[slot]: del timetable[slot]
            return False

        if fixed_eng102_session:
            fixed_slot_key = "Fri_5"
            fixed_room_name = "R5"
            if fixed_slot_key not in faculties[fixed_eng102_session['faculty']]['availability']:
                faculties[fixed_eng102_session['faculty']]['availability'].append(fixed_slot_key)
                faculties[fixed_eng102_session['faculty']]['availability'].sort(key=lambda x: int(x.split('_')[1]))
            if can_assign(fixed_slot_key, fixed_room_name, fixed_eng102_session, timetable):
                timetable.setdefault(fixed_slot_key, []).append({
                    "subject": fixed_eng102_session["name"],
                    "faculty": fixed_eng102_session["faculty"],
                    "batches": fixed_eng102_session["batches"],
                    "room": fixed_room_name,
                    "course_name": fixed_eng102_session["course_name"],
                    "section": fixed_eng102_session["section"],
                    "credit": fixed_eng102_session["credit"]
                })

        sessions.sort(key=lambda s: len(faculties[s["faculty"]]["availability"]))

        if assign_session(0):
            st.success("Timetable Generated Successfully!")

            # Display timetable
            st.subheader("Timetable")
            timetable_df = pd.DataFrame(index=SLOTS, columns=all_rooms_for_display)
            for slot_idx in SLOTS:
                slot_key = f"Fri_{slot_idx}"
                if slot_key in timetable:
                    for entry in timetable[slot_key]:
                        timetable_df.at[slot_idx, entry['room']] = f"{entry['subject']} ({entry['faculty']})"
            timetable_df.index = [TIME_MAP[s] for s in SLOTS]
            st.dataframe(timetable_df.fillna("---"))

            # Download
            csv_data = []
            for slot, entries in timetable.items():
                slot_num = int(slot.split('_')[1])
                for e in entries:
                    for batch in e['batches']:
                        csv_data.append({
                            "Batch": batch,
                            "Course Name": e['course_name'],
                            "Course Code": e['subject'],
                            "Initial": e['faculty'],
                            "Section": e['section'],
                            "Credit": e['credit'],
                            "Room": e['room'],
                            "Time": TIME_MAP[slot_num]
                        })
            # Sort by Batch (descending) to group batches together
            csv_data.sort(key=lambda x: x['Batch'], reverse=True)
            timetable_csv = pd.DataFrame(csv_data, columns=["Batch", "Course Name", "Course Code", "Initial", "Section", "Credit", "Room", "Time"]).to_csv(index=False)
            st.download_button("Download Detailed Batch Timetable CSV", timetable_csv, "detailed_batch_timetable.csv", "text/csv")
        else:
            st.error("Failed to generate timetable.")

    except Exception as e:
        st.error(f"Error: {str(e)}")
