import sqlite3

def initialize_deleted_data_db():
    conn = sqlite3.connect("deleted_data.db")
    cursor = conn.cursor()

    # Create the Deleted_Hostel_Data table with all tracking columns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Deleted_Hostel_Data (
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
            Remarks TEXT,
            Attachment TEXT,
            Aadhar_No TEXT,
            Deleted_At TEXT,      -- When it was backed up
            Modified_By TEXT,     -- Who updated the record
            Modified_At TEXT      -- When the update was made
        )
    ''')

    print("✅ Table 'Deleted_Hostel_Data' is ready in 'deleted_data.db'.")
    conn.commit()
    conn.close()

# Run the initializer
initialize_deleted_data_db()
