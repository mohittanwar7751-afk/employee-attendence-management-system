from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime, date
import json
import os
from typing import Dict, List, Any

app = Flask(__name__)
app.secret_key = 'crowdmuse-secret-key'

# Register custom filters
app.jinja_env.filters['zip'] = zip

# File to store data (resolve relative to this file so it works no matter the CWD)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

# Default data structure
default_data = {
    "admins": [
        {"id": 1, "username": "admin", "password": "admin"}
    ],
    "students": [
        {"id": 1, "name": "Demo User", "roll_no": "DEMO01", "email": "demo@example.com", "password": "password"}
    ],
    "attendance": {},  # Format: {"YYYY-MM-DD": {"student_id": "present/absent"}}
    # Weekly class scheduling + per-class attendance
    # "classes": [{"id": 1, "subject": "Math", "date": "YYYY-MM-DD", "time": "10:00", "admin_id": 1}],
    # "enrollments": {"<class_id>": ["<student_id>", ...]},
    # "class_attendance": {"<class_id>": {"YYYY-MM-DD": {"<student_id>": "present/absent"}}},
    "classes": [],
    "enrollments": {},
    "class_attendance": {},
    "locations": [
        {"id": 1, "name": "Main Library", "building": "Library", "floor": "Ground", "max_capacity": 200, "current_count": 45, "camera_id": "CAM-001", "icon": "fas fa-book", "color": "#3b82f6"},
        {"id": 2, "name": "Computer Lab", "building": "Science Block", "floor": "2nd", "max_capacity": 50, "current_count": 12, "camera_id": "CAM-002", "icon": "fas fa-laptop", "color": "#10b981"},
        {"id": 3, "name": "Cafeteria", "building": "Student Center", "floor": "Ground", "max_capacity": 150, "current_count": 89, "camera_id": "CAM-004", "icon": "fas fa-utensils", "color": "#ef4444"},
    ]
}

def load_data():
    """Load data from JSON file or create if doesn't exist"""
    if not os.path.exists(DATA_FILE):
        save_data(default_data)
        return default_data
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            # Backfill newer keys for older data.json files
            data.setdefault('admins', default_data['admins'])
            data.setdefault('students', default_data['students'])
            data.setdefault('attendance', {})
            data.setdefault('classes', [])
            data.setdefault('enrollments', {})
            data.setdefault('class_attendance', {})
            data.setdefault('locations', default_data['locations'])
            return data
    except Exception:
        return default_data


def _admin_required():
    """Return a redirect response if admin not logged in, else None."""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    return None


def _week_bounds(ref: date) -> Dict[str, date]:
    """Monday..Sunday bounds for the week containing ref."""
    start = ref.fromordinal(ref.toordinal() - ref.weekday())
    end = start.fromordinal(start.toordinal() + 6)
    return {"start": start, "end": end}


def _safe_parse_date(date_str: str) -> date | None:
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        return None

def save_data(data):
    """Save data to JSON file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_current_student(data):
    """Get logged in student object"""
    if 'student_id' not in session:
        return None
    return next((s for s in data["students"] if s['id'] == session['student_id']), None)

# --- ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        data = load_data()
        # Find user with matching email AND password
        user = next((s for s in data["students"] if s['email'] == email and s.get('password') == password), None)
        
        if user:
            session['student_id'] = user['id']
            session['user_name'] = user['name']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            
    return render_template('login.html')


@app.route('/')
def index():
    """Landing page: choose student or admin login"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Allow any random user to sign up"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        roll_no = request.form.get('roll_no')
        
        data = load_data()
        
        # Check if email already exists
        if any(s['email'] == email for s in data["students"]):
            flash('Email already registered. Please login.', 'error')
            return redirect(url_for('login'))
            
        # Create new student ID
        new_id = max([s['id'] for s in data["students"]]) + 1 if data["students"] else 1
        
        new_student = {
            "id": new_id,
            "name": name,
            "email": email,
            "password": password,
            "roll_no": roll_no
        }
        
        data["students"].append(new_student)
        save_data(data)
        
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        data = load_data()
        admin = next((a for a in data.get('admins', []) if a['username'] == username and a.get('password') == password), None)
        if admin:
            session.clear()
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials.', 'error')
    return render_template('admin_login.html')


@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        data = load_data()

        # Check if username already exists
        if any(a['username'] == username for a in data.get('admins', [])):
            flash('Username already registered. Please login.', 'error')
            return redirect(url_for('admin_login'))

        new_id = max([a['id'] for a in data.get('admins', [])]) + 1 if data.get('admins') else 1
        new_admin = {"id": new_id, "username": username, "password": password}
        data.setdefault('admins', []).append(new_admin)
        save_data(data)

        flash('Admin account created successfully! Please login.', 'success')
        return redirect(url_for('admin_login'))

    return render_template('admin_register.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))

    students = data.get('students', [])
    total_days = len(data.get('attendance', {}))
    return render_template('admin_dashboard.html', admin=admin, students=students, total_days=total_days)


@app.route('/admin/logout')
def admin_logout():
    # clear only admin-related session keys
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    data = load_data()
    current_student = get_current_student(data)
    if not current_student:
        return redirect(url_for('login'))

    # Calculate stats for THIS specific user
    today = date.today().isoformat()
    todays_attendance = data["attendance"].get(today, {})
    student_status = todays_attendance.get(str(current_student['id']), 'not_marked')
    
    total_days = len(data["attendance"])
    present_days = 0
    absent_days = 0
    
    for date_record in data["attendance"].values():
        status = date_record.get(str(current_student['id']), 'not_marked')
        if status == 'present':
            present_days += 1
        elif status == 'absent':
            absent_days += 1
            
    attendance_percentage = round((present_days / total_days * 100), 1) if total_days > 0 else 0
    
    stats = {
        'student_name': current_student['name'],
        'roll_no': current_student['roll_no'],
        'today_status': student_status,
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'attendance_percentage': attendance_percentage
    }
    
    return render_template('dashboard.html', stats=stats, formatted_date=datetime.now().strftime('%b %d, %Y'), student=current_student)

@app.route('/attendance')
def attendance():
    data = load_data()
    current_student = get_current_student(data)
    if not current_student:
        return redirect(url_for('login'))
        
    selected_date = request.args.get('date', date.today().isoformat())
    
    # Validation logic for date display
    try:
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
        formatted_date = date_obj.strftime('%A, %B %d, %Y')
    except:
        date_obj = date.today()
        selected_date = date_obj.isoformat()
        formatted_date = date_obj.strftime('%A, %B %d, %Y')
    
    todays_attendance = data["attendance"].get(selected_date, {})
    student_status = todays_attendance.get(str(current_student['id']), 'not_marked')
    
    history = []
    for date_str in sorted(data["attendance"].keys(), reverse=True):
        status = data["attendance"][date_str].get(str(current_student['id']), 'not_marked')
        if status != 'not_marked':
            history.append({
                'date': date_str,
                'formatted_date': datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y'),
                'status': status
            })
            
    return render_template('attendance.html', student=current_student, current_date=selected_date, current_status=student_status, formatted_date=formatted_date, attendance_history=history)

@app.route('/campus')
def campus():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    data = load_data()
    locations = data.get("locations", [])
    
    total_capacity = sum(loc['max_capacity'] for loc in locations)
    total_current = sum(loc['current_count'] for loc in locations)
    overall = round((total_current / total_capacity * 100), 1) if total_capacity > 0 else 0
    
    stats = {'total_locations': len(locations), 'total_capacity': total_capacity, 'total_current': total_current, 'overall_occupancy': overall}
    return render_template('campus.html', locations=locations, stats=stats)

@app.route('/reports')
def reports():
    # Keep the original logic but load from `load_data()`
    # (Simplified here to save space, copy your previous reports logic but add `data = load_data()` at the top)
    return redirect(url_for('dashboard'))


# --- ADMIN ROUTES ---

@app.route('/admin/students')
def admin_students():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))
    
    students = data.get('students', [])
    return render_template('admin_students.html', admin=admin, students=students)


@app.route('/admin/attendance')
def admin_attendance():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))
    
    attendance_records = data.get('attendance', {})
    return render_template('admin_attendance.html', admin=admin, attendance_records=attendance_records)


@app.route('/admin/reports')
def admin_reports():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))
    
    students = data.get('students', [])
    attendance_records = data.get('attendance', {})
    return render_template('admin_reports.html', admin=admin, students=students, attendance_records=attendance_records)


@app.route('/admin/locations')
def admin_locations():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))
    
    locations = data.get('locations', [])
    return render_template('admin_locations.html', admin=admin, locations=locations)


# --- NEW: WEEKLY CLASS ATTENDANCE ---

@app.route('/admin/classes/week')
def admin_weekly_class_schedule():
    gate = _admin_required()
    if gate:
        return gate

    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))

    today = date.today()
    bounds = _week_bounds(today)

    weekly_classes: List[Dict[str, Any]] = []
    for c in data.get('classes', []):
        if c.get('admin_id') != admin['id']:
            continue
        c_date = _safe_parse_date(c.get('date', ''))
        if not c_date:
            continue
        if bounds['start'] <= c_date <= bounds['end']:
            weekly_classes.append({
                **c,
                "date_obj": c_date,
                "formatted_date": c_date.strftime('%a, %b %d'),
            })

    weekly_classes.sort(key=lambda x: (x['date_obj'], x.get('time', '')))

    return render_template(
        'admin_weekly_schedule.html',
        admin=admin,
        week_start=bounds['start'],
        week_end=bounds['end'],
        weekly_classes=weekly_classes,
    )


@app.route('/admin/classes/<int:class_id>/attendance', methods=['GET'])
def admin_mark_attendance_view(class_id: int):
    gate = _admin_required()
    if gate:
        return gate

    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))

    cls = next((c for c in data.get('classes', []) if int(c.get('id', -1)) == class_id), None)
    if not cls or cls.get('admin_id') != admin['id']:
        flash('Class not found (or you do not have access).', 'error')
        return redirect(url_for('admin_weekly_class_schedule'))

    enrolled_ids = [int(sid) for sid in data.get('enrollments', {}).get(str(class_id), [])]
    students = [s for s in data.get('students', []) if int(s.get('id')) in enrolled_ids]
    students.sort(key=lambda s: s.get('name', '').lower())

    # Pre-fill defaults from already saved attendance (if any) for that date
    cls_date = cls.get('date')
    saved_for_date = (
        data.get('class_attendance', {})
            .get(str(class_id), {})
            .get(cls_date, {})
        if cls_date else {}
    )

    # Map student_id -> status
    existing_statuses: Dict[str, str] = {str(k): v for k, v in saved_for_date.items()} if isinstance(saved_for_date, dict) else {}

    return render_template(
        'admin_mark_attendance.html',
        admin=admin,
        cls=cls,
        students=students,
        existing_statuses=existing_statuses,
    )


@app.route('/admin/classes/<int:class_id>/attendance', methods=['POST'])
def admin_save_class_attendance(class_id: int):
    gate = _admin_required()
    if gate:
        return gate

    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))

    cls = next((c for c in data.get('classes', []) if int(c.get('id', -1)) == class_id), None)
    if not cls or cls.get('admin_id') != admin['id']:
        flash('Class not found (or you do not have access).', 'error')
        return redirect(url_for('admin_weekly_class_schedule'))

    enrolled_ids = [int(sid) for sid in data.get('enrollments', {}).get(str(class_id), [])]

    # Iterate all enrolled students and collect statuses from the POSTed form.
    # HTML uses name="status_<student_id>" => value present|absent
    statuses_for_class: Dict[str, str] = {}
    for student_id in enrolled_ids:
        key = f"status_{student_id}"
        status = request.form.get(key, 'present')
        status = status if status in ('present', 'absent') else 'present'
        statuses_for_class[str(student_id)] = status

    cls_date = cls.get('date') or date.today().isoformat()
    data.setdefault('class_attendance', {}).setdefault(str(class_id), {})[cls_date] = statuses_for_class

    save_data(data)
    flash('Attendance saved successfully!', 'success')
    return redirect(url_for('admin_mark_attendance_view', class_id=class_id))


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    port = int(os.environ.get('PORT', '5001'))
    app.run(debug=True, port=port)