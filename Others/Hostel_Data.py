import pandas as pd
import sqlite3
import os

# File paths
excel_file = 'Hostel_Data.xlsx'
sqlite_db = 'Hostel_Database.db'
table_name = 'Hostel_Data'

# Desired column order and clean version
desired_order = [
    "Sl.No", "Location", "Hostel_Type", "Building_Name_Number", "Room_Number",
    "Room_Capacity", "Status", "Employee_ID", "Employee_Name", "Department",
    "Designation", "Employment_Type", "Mobile_No", "Joining_Date","Aadhar_No",
    "Relieving_Date", "Emergency_Name","Emergency_Number","Emergency_Relation",
    "Attachment", "Remarks"
]
cleaned_order = [col.strip().replace(" ", "_").replace("/", "_") for col in desired_order]

# Step 1: Load Excel file
df = pd.read_excel(excel_file)

# Step 2: Reorder and clean column names
df = df[[col for col in desired_order if col in df.columns]]
df.columns = cleaned_order

# Step 3: Connect to SQLite
if os.path.exists(sqlite_db):
    os.remove(sqlite_db)  # optional: fresh rebuild
conn = sqlite3.connect(sqlite_db)
cursor = conn.cursor()

# Step 4: Create table manually with TEXT fields
cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {table_name} (
        Sl_No TEXT,
        Location TEXT,
        Hostel_Type TEXT,
        Building_Name_Number TEXT,
        Room_Number TEXT,
        Room_Capacity TEXT,
        Status TEXT,
        Employee_ID TEXT,
        Employee_Name TEXT,
        Department TEXT,
        Designation TEXT,
        Employment_Type TEXT,
        Mobile_No TEXT,
        Joining_Date TEXT,
        Relieving_Date TEXT,
        Attachment TEXT,
        Aadhar_No TEXT,
        Remarks TEXT,
        Emergency_Name TEXT,
        Emergency_Number TEXT,
        Emergency_Relation TEXT
    )
''')

# Step 5: Insert data
df.to_sql(table_name, conn, if_exists='replace', index=False)

# Step 6: Confirm insertion
cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
count = cursor.fetchone()[0]
conn.close()

print(f"✅ Successfully created table '{table_name}' with {count} rows in '{sqlite_db}'")