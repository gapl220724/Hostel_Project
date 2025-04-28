import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, session, render_template,send_file
from flask_session import Session
from flask_cors import CORS
from datetime import timedelta,datetime
import json
import pandas as pd
import io

app = Flask(__name__, static_folder='static')

# Configuration
app.secret_key = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
Session(app)
CORS(app)

DB_FILE = "Hostel_Database.db"

def ensure_deleted_table():
    conn = sqlite3.connect("deleted_data.db")
    cursor = conn.cursor()

    # Create the table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Deleted_Hostel_Data AS
        SELECT * FROM Hostel_Data WHERE 0
    """)

    # Ensure audit columns exist
    cursor.execute("PRAGMA table_info(Deleted_Hostel_Data)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    for col in ["Deleted_At", "Modified_By", "Modified_At"]:
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE Deleted_Hostel_Data ADD COLUMN {col} TEXT")

    conn.commit()
    conn.close()

# --- Load data from SQLite ---
def load_data():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM Hostel_Data").fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Route: Get paginated + filtered data ---
@app.route('/get-data', methods=['GET'])
def get_data():
    session['username'] = 'demo'  # Auto-login for dev/testing
    session['role'] = 'user'

    data = load_data()
    filters = request.args.to_dict(flat=False)

    # Clean filter keys (make sure they match SQLite column names)
    valid_keys = {
        "Location", "Hostel_Type", "Building_Name_Number", "Room_Number",
        "Status", "Employee_ID", "Department"
    }

    for key, values in filters.items():
        if key in ['page', 'limit']:
            continue
        clean_values = [v for v in values if v.strip()]
        if clean_values and key in valid_keys:
            data = [row for row in data if str(row.get(key)) in clean_values]

    # Pagination
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    start = (page - 1) * limit
    end = start + limit

    return jsonify({
        "data": data[start:end],
        "total": len(data),
        "page": page,
        "limit": limit
    })

#Add a new endpoint to get all distinct filter values:
@app.route('/get-filter-values', methods=['GET'])
def get_filter_values():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    filter_columns = [
        "Location", "Hostel_Type", "Building_Name_Number", "Room_Number",
        "Status", "Employee_ID", "Department"
    ]

    result = {}
    for col in filter_columns:
        cursor.execute(f"SELECT DISTINCT [{col}] FROM Hostel_Data WHERE [{col}] IS NOT NULL")
        result[col] = [row[0] for row in cursor.fetchall() if row[0]]

    conn.close()
    return jsonify(result)

# This allows the frontend to access the entire dataset for cascading filters.
@app.route('/get-full-data', methods=['GET'])
def get_full_data():
    return jsonify(load_data())

# --- Route:login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    remember = data.get("remember", False)

    with open("users.json") as f:
        users = json.load(f)

    role = None
    status = "failure"

    if username in users and users[username]["password"] == password:
        session["username"] = username
        session["role"] = users[username]["role"]
        session.permanent = remember
        role = users[username]["role"]
        status = "success"

    # Log the attempt
    with open("login_attempts.log", "a") as log_file:
        log_file.write(f"{datetime.now()} - User: {username} - {'Success' if status == 'success' else 'Failure'}\n")

    if status == "success":
        return jsonify({"status": "success", "role": role})
    else:
        return jsonify({"status": "failure", "message": "Invalid credentials"}), 401

# --- Route: logout
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "success"})

@app.route('/update-row', methods=['POST'])
def update_row():
    try:
        file = None  # Always define upfront

        # Check if the request is multipart/form-data (for file upload)
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            updated_data = request.form.to_dict()
            file = request.files.get('AttachmentFile')

        # If a file was uploaded, save it and update the 'Attachment' field
        if file and file.filename:
            # Construct filename: EmployeeName_EmployeeID_originalfilename.ext
            employee_name = updated_data.get('Employee_Name', 'Unknown').replace(" ", "").strip()
            employee_id = updated_data.get('Employee_ID', 'NA').strip()
            original_filename = file.filename.strip().replace(" ", "_")
            filename = f"{employee_name}_{employee_id}_{original_filename}"

            upload_path = os.path.join('static', 'uploads')
            os.makedirs(upload_path, exist_ok=True)
            file_path = os.path.join(upload_path, filename)
            file.save(file_path)

            updated_data['Attachment'] = filename

        # Use these fields to identify the correct row to update
        identifier_fields = ["Location", "Hostel_Type", "Building_Name_Number", "Room_Number","Room_Capacity"]
        conditions = " AND ".join([f"[{field}] = ?" for field in identifier_fields])
        identifiers = [updated_data.get(f"original_{field}") for field in identifier_fields]

        if None in identifiers:
            return jsonify({
                "status": "error",
                "message": f"Missing identifier fields: {identifiers}"
            }), 400

        # Connect to main DB and deleted DB
        conn_main = sqlite3.connect("Hostel_Database.db")
        conn_deleted = sqlite3.connect("deleted_data.db")
        conn_main.row_factory = conn_deleted.row_factory = sqlite3.Row
        cursor_main = conn_main.cursor()
        cursor_deleted = conn_deleted.cursor()

        # Fetch original row from main DB for backup
        old_row = cursor_main.execute(
            f"SELECT * FROM Hostel_Data WHERE {conditions}", identifiers
        ).fetchone()

        if old_row:
            old_data = dict(old_row)
            old_data.pop("Sl.No", None)  # Add this line to skip it
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            old_data["Deleted_At"] = now
            old_data["Modified_By"] = session.get("username", "unknown")
            old_data["Modified_At"] = now

            columns = ', '.join([f"[{col}]" for col in old_data.keys()])
            placeholders = ', '.join(['?'] * len(old_data))
            values = list(old_data.values())

            cursor_deleted.execute(
                f"INSERT INTO Deleted_Hostel_Data ({columns}) VALUES ({placeholders})",
                values
            )

            conn_deleted.commit()
        # Prepare data for update
        # Allow empty strings; just skip keys that are metadata like 'original_X'
        fields = [k for k in updated_data.keys() if not k.startswith("original_")]
        set_clause = ', '.join([f"[{f}] = ?" for f in fields])
        values = [updated_data[f] for f in fields]

        # Debug info
        print("SQL SET clause:", set_clause)
        print("Values to update:", values)
        print("Identifiers (WHERE clause):", identifiers)

        # Perform the update in the main DB
        cursor_main.execute(
            f"UPDATE Hostel_Data SET {set_clause} WHERE {conditions}",
            values + identifiers
        )
        conn_main.commit()

        # Close both connections
        conn_main.close()
        conn_deleted.close()

        return jsonify({"status": "success"})

    except Exception as e:
        import traceback
        print("Error in /update-row:", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/delete-attachment', methods=['POST'])
def delete_attachment():
    data = request.get_json()
    attachment = data.get("Attachment")
    identifiers = [data.get(k) for k in ["Location", "Hostel_Type", "Building_Name_Number", "Room_Number"]]

    if not attachment or None in identifiers:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    # Move attachment to archive folder
    original_path = os.path.join('static', 'uploads', attachment)
    archive_path = os.path.join('static', 'archive')
    os.makedirs(archive_path, exist_ok=True)

    if os.path.exists(original_path):
        os.rename(original_path, os.path.join(archive_path, attachment))

    # Update DB: remove attachment reference
    conn = sqlite3.connect("Hostel_Database.db")
    cursor = conn.cursor()
    conditions = " AND ".join([f"[{field}] = ?" for field in ["Location", "Hostel_Type", "Building_Name_Number", "Room_Number"]])
    cursor.execute(f"UPDATE Hostel_Data SET Attachment = '' WHERE {conditions}", identifiers)
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

@app.route('/export-deleted-data', methods=['GET'])
def export_deleted_data():
    # Connect to the correct databases
    conn_deleted = sqlite3.connect("deleted_data.db")
    conn_current = sqlite3.connect(DB_FILE)  # DB_FILE = "Hostel_Database.db"

    # Load data from each DB
    df = pd.read_sql_query("SELECT * FROM Deleted_Hostel_Data", conn_deleted)
    current_df = pd.read_sql_query("SELECT * FROM Hostel_Data", conn_current)

    conn_deleted.close()
    conn_current.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='DeletedData')
        workbook = writer.book
        worksheet = writer.sheets['DeletedData']

        # Highlight format (light yellow)
        highlight_format = workbook.add_format({'bg_color': '#FFF3CD'})  

        deleted_columns = list(df.columns)
        emp_id_col = "Employee_ID"

        for row_num, (_, deleted_row) in enumerate(df.iterrows(), start=1):
            emp_id = deleted_row.get(emp_id_col)
            current_row = current_df[current_df[emp_id_col] == emp_id]

            if not current_row.empty:
                current_row = current_row.iloc[0]

                for col_num, col in enumerate(deleted_columns):
                    if col == "Deleted_At":
                        continue  # Don't compare Deleted_At
                    deleted_val = deleted_row.get(col)
                    current_val = current_row.get(col)
                    # Only highlight if values differ
                    if pd.notna(deleted_val) and pd.notna(current_val) and str(deleted_val) != str(current_val):
                        worksheet.write(row_num, col_num, deleted_val, highlight_format)

    output.seek(0)

    today_str = datetime.now().strftime('%Y-%m-%d')
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"Deleted_Data_Excel_{today_str}.xlsx"
    )
# --- Route: Serve frontend ---

@app.route('/')
def serve_index():
    return render_template('index.html')

if __name__ == '__main__':
    ensure_deleted_table()
    app.run(debug=True)


#pip install XlsxWriter on cmd or terminal (install both openpyxl as well. Both for excel)