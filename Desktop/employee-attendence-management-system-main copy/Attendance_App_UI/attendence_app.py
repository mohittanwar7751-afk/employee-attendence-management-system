from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, Response
from datetime import datetime, date
import json
import os
import csv
import io
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


def _get_merged_student_records(data: dict, student_id: str) -> dict:
    """Merge attendance records for one student from both data sources.

    Sources (in priority order — later overwrites earlier for same date):
      1. class_attendance  {class_id -> {date -> {student_id -> status}}}
      2. attendance        {date -> {student_id -> info}}

    Returns: {date_str: {'status': str, 'time': str}}
    """
    records: Dict[str, dict] = {}

    # Pass 1 — class_attendance (lower priority)
    for _, class_dates in data.get('class_attendance', {}).items():
        if not isinstance(class_dates, dict):
            continue
        for date_str, day_map in class_dates.items():
            if not isinstance(day_map, dict):
                continue
            if student_id in day_map and date_str not in records:
                info     = day_map[student_id]
                status   = info if isinstance(info, str) else info.get('status', 'present')
                time_val = '' if isinstance(info, str) else info.get('time', '')
                records[date_str] = {'status': status, 'time': time_val}

    # Pass 2 — direct attendance (higher priority, overwrites)
    for date_str, day_records in data.get('attendance', {}).items():
        if not isinstance(day_records, dict):
            continue
        if student_id in day_records:
            info     = day_records[student_id]
            status   = info if isinstance(info, str) else info.get('status', 'present')
            time_val = '' if isinstance(info, str) else info.get('time', '')
            records[date_str] = {'status': status, 'time': time_val}

    return records

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

    sid = str(current_student['id'])

    # Merge attendance from both class_attendance and direct attendance
    merged = _get_merged_student_records(data, sid)

    today = date.today().isoformat()
    today_rec = merged.get(today, {})
    student_status = today_rec.get('status', 'not_marked') if today_rec else 'not_marked'

    total_days   = len(merged)
    present_days = sum(1 for r in merged.values() if r['status'] == 'present')
    absent_days  = sum(1 for r in merged.values() if r['status'] == 'absent')
    late_days    = sum(1 for r in merged.values() if r['status'] == 'late')

    attendance_percentage = round((present_days / total_days * 100), 1) if total_days > 0 else 0

    stats = {
        'student_name':        current_student['name'],
        'roll_no':             current_student['roll_no'],
        'today_status':        student_status,
        'total_days':          total_days,
        'present_days':        present_days,
        'absent_days':         absent_days,
        'late_days':           late_days,
        'attendance_percentage': attendance_percentage,
    }

    return render_template('dashboard.html', stats=stats,
                           formatted_date=datetime.now().strftime('%b %d, %Y'),
                           student=current_student)

@app.route('/attendance')
def attendance():
    data = load_data()
    current_student = get_current_student(data)
    if not current_student:
        return redirect(url_for('login'))

    sid = str(current_student['id'])

    # Validate selected date
    selected_date = request.args.get('date', date.today().isoformat())
    try:
        date_obj      = datetime.strptime(selected_date, '%Y-%m-%d').date()
        formatted_date = date_obj.strftime('%A, %B %d, %Y')
    except Exception:
        date_obj      = date.today()
        selected_date = date_obj.isoformat()
        formatted_date = date_obj.strftime('%A, %B %d, %Y')

    # Merge records from both data sources
    merged = _get_merged_student_records(data, sid)

    # Status for the currently selected date
    today_rec      = merged.get(selected_date, {})
    current_status = today_rec.get('status', 'not_marked') if today_rec else 'not_marked'

    # Build attendance history (sorted newest first)
    history = []
    for date_str in sorted(merged.keys(), reverse=True):
        rec = merged[date_str]
        history.append({
            'date':           date_str,
            'formatted_date': datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y'),
            'status':         rec['status'],
            'time':           rec.get('time', ''),
        })

    return render_template(
        'attendance.html',
        student=current_student,
        current_date=selected_date,
        current_status=current_status,
        formatted_date=formatted_date,
        attendance_history=history,
    )

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
    data = load_data()
    current_student = get_current_student(data)
    if not current_student:
        return redirect(url_for('login'))

    sid = str(current_student['id'])
    merged = _get_merged_student_records(data, sid)

    total_days = len(merged)
    present_days = sum(1 for r in merged.values() if r['status'] == 'present')
    absent_days = sum(1 for r in merged.values() if r['status'] == 'absent')
    late_days = sum(1 for r in merged.values() if r['status'] == 'late')
    percentage = round((present_days / total_days * 100), 1) if total_days else 0

    # Monthly breakdown
    monthly_bucket: Dict[str, Dict[str, int]] = {}
    for date_str, rec in merged.items():
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            continue
        key = dt.strftime('%b %Y')
        b = monthly_bucket.setdefault(key, {'present': 0, 'absent': 0, 'late': 0, 'total': 0})
        b['total'] += 1
        if rec['status'] == 'present':
            b['present'] += 1
        elif rec['status'] == 'absent':
            b['absent'] += 1
        elif rec['status'] == 'late':
            b['late'] += 1

    monthly_breakdown = []
    for month in sorted(monthly_bucket.keys(), key=lambda m: datetime.strptime(m, '%b %Y')):
        b = monthly_bucket[month]
        month_pct = round((b['present'] / b['total'] * 100), 1) if b['total'] else 0
        monthly_breakdown.append({
            'month': month,
            'present': b['present'],
            'absent': b['absent'],
            'late': b['late'],
            'total': b['total'],
            'percentage': month_pct,
        })

    # Daily records (newest first)
    daily_records = []
    for date_str in sorted(merged.keys(), reverse=True):
        rec = merged[date_str]
        try:
            formatted = datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y')
        except ValueError:
            formatted = date_str
        daily_records.append({
            'date': date_str,
            'formatted_date': formatted,
            'status': rec['status'],
            'time': rec.get('time', ''),
        })

    stats = {
        'student': current_student,
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'percentage': percentage,
        'monthly_breakdown': monthly_breakdown,
        'daily_records': daily_records,
    }

    return render_template('reports.html', stats=stats)


@app.route('/timetable')
def student_timetable():
    """Student page: weekly timetable (same source of truth as admin weekly classes)."""
    data = load_data()
    current_student = get_current_student(data)
    if not current_student:
        return redirect(url_for('login'))

    today = date.today()
    bounds = _week_bounds(today)

    sid = str(current_student['id'])
    enrollments = data.get('enrollments', {}) or {}

    # Find classes where current student is enrolled and that fall within current week
    weekly_classes: List[Dict[str, Any]] = []
    for c in data.get('classes', []):
        c_id = str(c.get('id'))
        if sid not in [str(x) for x in enrollments.get(c_id, [])]:
            continue
        c_date = _safe_parse_date(c.get('date', ''))
        if not c_date:
            continue
        if bounds['start'] <= c_date <= bounds['end']:
            weekly_classes.append({
                **c,
                'date_obj': c_date,
                'formatted_date': c_date.strftime('%a, %b %d'),
            })

    weekly_classes.sort(key=lambda x: (x['date_obj'], x.get('time', '')))

    return render_template(
        'student_timetable.html',
        student=current_student,
        formatted_date=datetime.now().strftime('%b %d, %Y'),
        week_start=bounds['start'],
        week_end=bounds['end'],
        weekly_classes=weekly_classes,
    )


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


@app.route('/admin/students/add', methods=['POST'])
def admin_student_add():
    """API: Add a new student. Returns JSON."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    name     = request.form.get('name', '').strip()
    email    = request.form.get('email', '').strip().lower()
    roll_no  = request.form.get('roll_no', '').strip()
    password = request.form.get('password', '').strip()

    # --- Validation ---
    errors = []
    if not name:
        errors.append('Name is required.')
    if not email or '@' not in email:
        errors.append('A valid email is required.')
    if not roll_no:
        errors.append('Roll number is required.')
    if not password:
        errors.append('Password is required.')
    if errors:
        return jsonify({'success': False, 'message': ' '.join(errors)}), 400

    data = load_data()
    students = data.get('students', [])

    # --- Duplicate checks ---
    if any(s['email'].lower() == email for s in students):
        return jsonify({'success': False, 'message': f'Email "{email}" is already registered.'}), 409
    if any(s.get('roll_no', '').lower() == roll_no.lower() for s in students):
        return jsonify({'success': False, 'message': f'Roll number "{roll_no}" already exists.'}), 409

    # --- Create student ---
    new_id = max((s['id'] for s in students), default=0) + 1
    new_student = {
        'id':       new_id,
        'name':     name,
        'email':    email,
        'roll_no':  roll_no,
        'password': password,
    }
    data['students'].append(new_student)
    save_data(data)

    return jsonify({
        'success': True,
        'message': f'Student "{name}" added successfully.',
        'student': new_student,
    })


@app.route('/admin/students/delete', methods=['POST'])
def admin_student_delete():
    """API: Delete a student by ID. Returns JSON."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    student_id = request.form.get('student_id', '').strip()
    if not student_id:
        return jsonify({'success': False, 'message': 'Student ID is required.'}), 400

    data = load_data()
    students = data.get('students', [])
    student  = next((s for s in students if str(s['id']) == student_id), None)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found.'}), 404

    # Remove from students list
    data['students'] = [s for s in students if str(s['id']) != student_id]

    # Clean up direct attendance records for this student
    for date_str in list(data.get('attendance', {}).keys()):
        data['attendance'][date_str].pop(student_id, None)
        if not data['attendance'][date_str]:
            del data['attendance'][date_str]

    save_data(data)
    return jsonify({'success': True, 'message': f'Student "{student["name"]}" deleted.'})


@app.route('/admin/attendance')
def admin_attendance():
    """Admin page: full attendance records management with add/edit/delete/filter/export.
    
    Merges two data sources:
      1. data['attendance']       => direct/manual records  {date: {student_id: info}}
      2. data['class_attendance'] => per-class records      {class_id: {date: {student_id: status}}}
    Records from source-1 take precedence when the same student+date exists in both.
    """
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))

    students      = data.get('students', [])
    attendance    = data.get('attendance', {})        # direct records
    class_attend  = data.get('class_attendance', {})  # per-class records

    # ── Helper: resolve student object by string id ──────────────────────
    def get_student(sid_str):
        return next((s for s in students if str(s['id']) == sid_str), None)

    # ── 1. Collect all records into a dict keyed by (date, student_id)
    #       so duplicates are silently merged (direct records win).
    merged: Dict[tuple, dict] = {}

    # First pass: class_attendance (lower priority)
    for class_id_str, class_dates in class_attend.items():
        if not isinstance(class_dates, dict):
            continue
        for date_str, day_map in class_dates.items():
            if not isinstance(day_map, dict):
                continue
            for sid_str, info in day_map.items():
                key = (date_str, sid_str)
                if key in merged:
                    continue  # will be overwritten by direct record if it exists
                status   = info if isinstance(info, str) else info.get('status', 'present')
                time_val = '' if isinstance(info, str) else info.get('time', '')
                student  = get_student(sid_str)
                merged[key] = {
                    'date':         date_str,
                    'student_id':   sid_str,
                    'student_name': student['name'] if student else f'ID {sid_str}',
                    'roll_no':      student.get('roll_no', '') if student else '',
                    'status':       status,
                    'time':         time_val,
                }

    # Second pass: direct attendance (higher priority — overwrites class entries)
    for date_str, day_records in attendance.items():
        if not isinstance(day_records, dict):
            continue
        for sid_str, info in day_records.items():
            status   = info if isinstance(info, str) else info.get('status', 'present')
            time_val = '' if isinstance(info, str) else info.get('time', '')
            student  = get_student(sid_str)
            merged[(date_str, sid_str)] = {
                'date':         date_str,
                'student_id':   sid_str,
                'student_name': student['name'] if student else f'ID {sid_str}',
                'roll_no':      student.get('roll_no', '') if student else '',
                'status':       status,
                'time':         time_val,
            }

    # ── 2. Flatten + sort (newest date first, then alpha by name) ─────────
    def sort_key(r):
        try:
            ts = -datetime.strptime(r['date'], '%Y-%m-%d').timestamp()
        except ValueError:
            ts = 0
        return (ts, r['student_name'].lower())

    flat_records = sorted(merged.values(), key=sort_key)

    # ── 3. Summary statistics ─────────────────────────────────────────────
    summary = {
        'total':   len(flat_records),
        'present': sum(1 for r in flat_records if r['status'] == 'present'),
        'absent':  sum(1 for r in flat_records if r['status'] == 'absent'),
        'late':    sum(1 for r in flat_records if r['status'] == 'late'),
    }

    return render_template(
        'admin_attendance.html',
        admin=admin,
        students=students,
        records=flat_records,
        summary=summary,
        today=date.today().isoformat(),
    )


# ── Attendance Records API ────────────────────────────────────────────────

@app.route('/admin/attendance/add', methods=['POST'])
def admin_attendance_add():
    """API: Add a new attendance record. Returns JSON."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    # Read form fields
    student_id = request.form.get('student_id', '').strip()
    record_date = request.form.get('date', '').strip()
    status = request.form.get('status', '').strip().lower()
    time_val = request.form.get('time', '').strip()

    # ── Validation ────────────────────────────────────────────────────────
    errors = []
    if not student_id:
        errors.append('Student is required.')
    if not record_date:
        errors.append('Date is required.')
    else:
        try:
            datetime.strptime(record_date, '%Y-%m-%d')
        except ValueError:
            errors.append('Invalid date format.')
    if status not in ('present', 'absent', 'late'):
        errors.append('Status must be Present, Absent, or Late.')
    if errors:
        return jsonify({'success': False, 'message': ' '.join(errors)}), 400

    data = load_data()

    # Verify student exists
    student = next((s for s in data.get('students', []) if str(s['id']) == student_id), None)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found.'}), 404

    # ── Duplicate check ──────────────────────────────────────────────────
    day_records = data['attendance'].setdefault(record_date, {})
    if student_id in day_records:
        return jsonify({'success': False, 'message': f'Attendance already recorded for {student["name"]} on {record_date}.'}), 409

    # ── Store record (dict format to support time + status) ──────────────
    day_records[student_id] = {'status': status, 'time': time_val}
    save_data(data)

    return jsonify({
        'success': True,
        'message': f'Attendance marked for {student["name"]} on {record_date}.',
        'record': {
            'date': record_date,
            'student_id': student_id,
            'student_name': student['name'],
            'roll_no': student.get('roll_no', ''),
            'status': status,
            'time': time_val,
        }
    })


@app.route('/admin/attendance/edit', methods=['POST'])
def admin_attendance_edit():
    """API: Edit an existing attendance record. Identified by student_id + date."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    student_id = request.form.get('student_id', '').strip()
    record_date = request.form.get('date', '').strip()
    new_status = request.form.get('status', '').strip().lower()
    new_time = request.form.get('time', '').strip()

    if new_status not in ('present', 'absent', 'late'):
        return jsonify({'success': False, 'message': 'Invalid status.'}), 400

    data = load_data()
    day_records = data['attendance'].get(record_date, {})
    if student_id not in day_records:
        return jsonify({'success': False, 'message': 'Record not found.'}), 404

    day_records[student_id] = {'status': new_status, 'time': new_time}
    save_data(data)

    student = next((s for s in data.get('students', []) if str(s['id']) == student_id), None)
    return jsonify({
        'success': True,
        'message': 'Record updated successfully.',
        'record': {
            'date': record_date,
            'student_id': student_id,
            'student_name': student['name'] if student else '',
            'roll_no': student.get('roll_no', '') if student else '',
            'status': new_status,
            'time': new_time,
        }
    })


@app.route('/admin/attendance/delete', methods=['POST'])
def admin_attendance_delete():
    """API: Delete an attendance record identified by student_id + date."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    student_id = request.form.get('student_id', '').strip()
    record_date = request.form.get('date', '').strip()

    data = load_data()
    day_records = data['attendance'].get(record_date, {})
    if student_id not in day_records:
        return jsonify({'success': False, 'message': 'Record not found.'}), 404

    del day_records[student_id]
    # Clean up empty date keys
    if not day_records:
        del data['attendance'][record_date]
    save_data(data)

    return jsonify({'success': True, 'message': 'Record deleted successfully.'})


@app.route('/admin/attendance/export')
def admin_attendance_export():
    """Export ALL attendance records (direct + class_attendance) as CSV."""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    data = load_data()
    students     = data.get('students', [])
    attendance   = data.get('attendance', {})
    class_attend = data.get('class_attendance', {})

    def get_student(sid_str):
        return next((s for s in students if str(s['id']) == sid_str), None)

    # Merge both sources (same logic as the view)
    merged: Dict[tuple, dict] = {}

    for _, class_dates in class_attend.items():
        if not isinstance(class_dates, dict):
            continue
        for date_str, day_map in class_dates.items():
            if not isinstance(day_map, dict):
                continue
            for sid, info in day_map.items():
                key = (date_str, sid)
                if key not in merged:
                    status   = info if isinstance(info, str) else info.get('status', 'present')
                    time_val = '' if isinstance(info, str) else info.get('time', '')
                    merged[key] = {'date': date_str, 'sid': sid, 'status': status, 'time': time_val}

    for date_str, day_records in attendance.items():
        if not isinstance(day_records, dict):
            continue
        for sid, info in day_records.items():
            status   = info if isinstance(info, str) else info.get('status', 'present')
            time_val = '' if isinstance(info, str) else info.get('time', '')
            merged[(date_str, sid)] = {'date': date_str, 'sid': sid, 'status': status, 'time': time_val}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Student ID', 'Student Name', 'Roll No', 'Status', 'Time'])
    for (date_str, sid), r in sorted(merged.items(), key=lambda x: x[0][0], reverse=True):
        student = get_student(sid)
        writer.writerow([
            r['date'],
            sid,
            student['name'] if student else '',
            student.get('roll_no', '') if student else '',
            r['status'].capitalize(),
            r['time'],
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=attendance_records_{date.today().isoformat()}.csv'}
    )


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

    # Pass ALL classes (not just this week) for the enrollment modal
    all_classes = [
        c for c in data.get('classes', [])
        if c.get('admin_id') == admin['id']
    ]
    all_classes.sort(key=lambda c: (c.get('date', ''), c.get('time', '')))

    return render_template(
        'admin_weekly_schedule.html',
        admin=admin,
        week_start=bounds['start'],
        week_end=bounds['end'],
        weekly_classes=weekly_classes,
        all_classes=all_classes,
        students=data.get('students', []),
        enrollments=data.get('enrollments', {}),
    )


# ── Timetable editor (classes CRUD-lite) ─────────────────────────────────

@app.route('/admin/classes/new', methods=['GET', 'POST'])
def admin_class_new():
    """Create a new class (timetable entry)."""
    gate = _admin_required()
    if gate:
        return gate

    data = load_data()
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    if not admin:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        subject = (request.form.get('subject') or '').strip()
        date_str = (request.form.get('date') or '').strip()
        time_str = (request.form.get('time') or '').strip()

        errors = []
        if not subject:
            errors.append('Subject is required.')
        if not _safe_parse_date(date_str):
            errors.append('Valid date (YYYY-MM-DD) is required.')
        if not time_str:
            errors.append('Time is required.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            new_id = max((int(c.get('id', 0)) for c in data.get('classes', [])), default=0) + 1
            new_class = {
                'id': new_id,
                'subject': subject,
                'date': date_str,
                'time': time_str,
                'admin_id': admin['id'],
            }
            data.setdefault('classes', []).append(new_class)
            # Ensure an enrollments bucket exists for this class
            data.setdefault('enrollments', {}).setdefault(str(new_id), [])
            save_data(data)
            flash('Class created successfully.', 'success')
            return redirect(url_for('admin_weekly_class_schedule'))

    return render_template('admin_class_form.html', admin=admin, mode='new', cls=None)


@app.route('/admin/classes/<int:class_id>/edit', methods=['GET', 'POST'])
def admin_class_edit(class_id: int):
    """Edit an existing class (timetable entry)."""
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

    if request.method == 'POST':
        subject = (request.form.get('subject') or '').strip()
        date_str = (request.form.get('date') or '').strip()
        time_str = (request.form.get('time') or '').strip()

        errors = []
        if not subject:
            errors.append('Subject is required.')
        if not _safe_parse_date(date_str):
            errors.append('Valid date (YYYY-MM-DD) is required.')
        if not time_str:
            errors.append('Time is required.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            cls['subject'] = subject
            cls['date'] = date_str
            cls['time'] = time_str
            save_data(data)
            flash('Class updated successfully.', 'success')
            return redirect(url_for('admin_weekly_class_schedule'))

    return render_template('admin_class_form.html', admin=admin, mode='edit', cls=cls)


# ── Enrollment API ────────────────────────────────────────────────────────

@app.route('/admin/classes/<int:class_id>/enrollments', methods=['GET'])
def admin_class_enrollment_get(class_id: int):
    """Return current enrolled student IDs for a class as JSON."""
    gate = _admin_required()
    if gate:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    data = load_data()
    enrolled_ids = data.get('enrollments', {}).get(str(class_id), [])
    return jsonify({'success': True, 'enrolled': [str(sid) for sid in enrolled_ids]})


@app.route('/admin/classes/<int:class_id>/enrollments', methods=['POST'])
def admin_class_enrollment_save(class_id: int):
    """Replace the enrollment list for a class. Accepts student_ids[] in POST body."""
    gate = _admin_required()
    if gate:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    data = load_data()

    # Verify class exists and belongs to this admin
    admin = next((a for a in data.get('admins', []) if a['id'] == session.get('admin_id')), None)
    cls = next((c for c in data.get('classes', []) if int(c.get('id', -1)) == class_id), None)
    if not cls or (admin and cls.get('admin_id') != admin['id']):
        return jsonify({'success': False, 'message': 'Class not found.'}), 404

    # getlist returns all values for student_ids[]
    new_ids = request.form.getlist('student_ids')
    # Validate every id actually exists
    valid_ids = {str(s['id']) for s in data.get('students', [])}
    new_ids   = [sid for sid in new_ids if sid in valid_ids]

    data.setdefault('enrollments', {})[str(class_id)] = new_ids
    save_data(data)

    return jsonify({
        'success': True,
        'message': f'{len(new_ids)} student(s) enrolled in "{cls["subject"]}".',
        'enrolled': new_ids,
        'count': len(new_ids),
    })


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
    port = int(os.environ.get('PORT', '5007'))
    app.run(debug=True, port=port)