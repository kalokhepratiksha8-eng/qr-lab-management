from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
import qrcode
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'qrlab_secret_2024'

# ─────────────────────────────────────────────
#  DATABASE CONNECTION  — change password here
# ─────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="P@K!2816#P",   # ← YOUR MySQL password
        database="lab_equipment_db"
    )

# ─────────────────────────────────────────────
#  LOGIN REQUIRED DECORATOR
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
#  LOGIN / LOGOUT
# ─────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            user = cursor.fetchone()
            db.close()
            if user:
                session['username'] = user['username']
                session['role'] = user.get('role', 'Admin')
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password.', 'error')
        except Exception as e:
            flash(f'DB Error: {e}', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
@app.route('/')
@login_required
def home():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as cnt FROM lab")
    lab_count = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM equipment")
    eq_count = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM pc")
    pc_count = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM department")
    dep_count = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM equipment WHERE status='Working'")
    eq_working = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM equipment WHERE status!='Working'")
    eq_notworking = cursor.fetchone()['cnt']

    # Recent equipment for dashboard table
    cursor.execute("""
        SELECT e.*, l.lab_name FROM equipment e
        LEFT JOIN lab l ON e.lab_id = l.lab_id
        LIMIT 6
    """)
    recent_equipment = cursor.fetchall()

    db.close()
    return render_template('index.html',
        lab_count=lab_count,
        eq_count=eq_count,
        pc_count=pc_count,
        dep_count=dep_count,
        eq_working=eq_working,
        eq_notworking=eq_notworking,
        recent_equipment=recent_equipment
    )

# ─────────────────────────────────────────────
#  LABS
# ─────────────────────────────────────────────
@app.route('/labs')
@login_required
def labs():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT l.*, d.dep_name
        FROM lab l
        JOIN department d ON l.dep_id = d.dep_id
    """)
    labs = cursor.fetchall()
    db.close()
    return render_template('labs.html', labs=labs)

@app.route('/lab/<int:lab_id>')
@login_required
def lab_detail(lab_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT l.*, d.dep_name
        FROM lab l JOIN department d ON l.dep_id = d.dep_id
        WHERE l.lab_id = %s
    """, (lab_id,))
    lab = cursor.fetchone()
    if not lab:
        db.close()
        flash('Lab not found.', 'error')
        return redirect(url_for('labs'))
    cursor.execute("SELECT * FROM equipment WHERE lab_id = %s", (lab_id,))
    equipment = cursor.fetchall()
    cursor.execute("SELECT * FROM pc WHERE lab_id = %s", (lab_id,))
    pcs = cursor.fetchall()
    db.close()
    return render_template('lab_detail.html', lab=lab, equipment=equipment, pcs=pcs)

# ─────────────────────────────────────────────
#  EQUIPMENT
# ─────────────────────────────────────────────
@app.route('/equipment')
@login_required
def equipment():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, l.lab_name
        FROM equipment e
        LEFT JOIN lab l ON e.lab_id = l.lab_id
        ORDER BY e.lab_id, e.equipment_name
    """)
    equipments = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as cnt FROM equipment WHERE status='Working'")
    eq_working = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM equipment WHERE status!='Working'")
    eq_not_working = cursor.fetchone()['cnt']
    eq_total = len(equipments)
    db.close()
    return render_template('equipment.html',
        equipments=equipments,
        eq_working=eq_working,
        eq_not_working=eq_not_working,
        eq_total=eq_total
    )

# ─────────────────────────────────────────────
#  SOFTWARE
# ─────────────────────────────────────────────
@app.route('/software')
@login_required
def software():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM software
        ORDER BY software_name
    """)
    softwares = cursor.fetchall()
    db.close()
    return render_template('software.html', softwares=softwares)

# ─────────────────────────────────────────────
#  DEPARTMENTS
# ─────────────────────────────────────────────
@app.route('/departments')
@login_required
def departments():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT d.*, COUNT(l.lab_id) as lab_count
        FROM department d
        LEFT JOIN lab l ON d.dep_id = l.dep_id
        GROUP BY d.dep_id
    """)
    departments = cursor.fetchall()
    db.close()
    return render_template('departments.html', departments=departments)

# ─────────────────────────────────────────────
#  QR CODE GENERATION
# ─────────────────────────────────────────────
@app.route('/generate_qr/<int:lab_id>')
@login_required
def generate_qr(lab_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT l.*, d.dep_name
        FROM lab l JOIN department d ON l.dep_id = d.dep_id
        WHERE l.lab_id = %s
    """, (lab_id,))
    lab = cursor.fetchone()
    db.close()
    if not lab:
        flash('Lab not found.', 'error')
        return redirect(url_for('labs'))

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    qr_data = f"http://{local_ip}:5000/lab/{lab_id}"
    qr_img = qrcode.make(qr_data)
    qr_dir = os.path.join('static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)
    qr_path = os.path.join(qr_dir, f"lab_{lab_id}.png")
    qr_img.save(qr_path)

    return render_template('qr_code.html',
        lab=lab,
        qr_image=f"qrcodes/lab_{lab_id}.png",
        qr_url=qr_data
    )

# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
