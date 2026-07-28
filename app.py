from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import os
import threading
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import threading
# Import the launcher function from your background agent script
from agent import start_telegram_bot  

# Initial configuration loaders
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'royal_ledger_super_secure_vault_key')
app.config['UPLOAD_FOLDER'] = 'static/uploads/'

# Ensure upload directory exists for profile pictures
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Define a shared path fallback checking whether the app runs locally or on production servers
DB_PATH = '/data/finance.db' if os.path.exists('/data') else 'finance.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Users Security Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            profile_pic TEXT DEFAULT 'default_profile.png'
        )
    ''')
    
    # 2. Transaction Ledger Database Schema Integration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,          -- 'income' or 'expense'
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# ==========================================
# AUTHENTICATION PORTAL GATEWAYS
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, password, profile_pic FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            session['profile_pic'] = user[2]
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid Username or Password.")
            
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    hashed_password = generate_password_hash(password)
    
    file = request.files.get('profile_pic')
    filename = 'default_profile.png'
    
    if file and file.filename != '':
        filename = secure_filename(f"{username}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, profile_pic) VALUES (?, ?, ?)", 
                       (username, hashed_password, filename))
        conn.commit()
        conn.close()
        return render_template('login.html', success="Registration successful! Sign in below.")
    except sqlite3.IntegrityError:
        return render_template('login.html', error="That username is already taken.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# GLOBAL LOGIN ENFORCEMENT GUARD
# ==========================================
@app.before_request
def require_login():
    allowed_routes = ['login', 'register', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

# ==========================================
# TEMPLATE CONTROLLER LINKS
# ==========================================

@app.route('/')
def index(): 
    return render_template('index.html', username=session.get('username'), profile_pic=session.get('profile_pic'))

@app.route('/income')
def income(): 
    return render_template('income.html', username=session.get('username'), profile_pic=session.get('profile_pic'))

@app.route('/expense')
def expense(): 
    return render_template('expense.html', username=session.get('username'), profile_pic=session.get('profile_pic'))

@app.route('/dailyhistory')
def dailyhistory(): 
    return render_template('dailyhistory.html', username=session.get('username'), profile_pic=session.get('profile_pic'))

@app.route('/weekly')
def weekly(): 
    return render_template('weekly.html', username=session.get('username'), profile_pic=session.get('profile_pic'))

@app.route('/monthly')
def monthly(): 
    return render_template('monthly.html', username=session.get('username'), profile_pic=session.get('profile_pic'))

# ==========================================
# TRANSACTION FETCH / SUBMIT DATA PIPELINE
# ==========================================

@app.route('/api/transactions', methods=['GET', 'POST'])
def handle_transactions():
    user_id = session.get('user_id')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        try:
            data = request.json
            
            # Form Validation: Parses frontend input strings directly into local date values
            input_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            today = date.today()
            
            if input_date < today:
                conn.close()
                return jsonify({"status": "error", "message": "Date selection must start from today onwards!"}), 400
                
            cursor.execute(
                "INSERT INTO transactions (user_id, type, amount, category, date, note) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, data['type'], float(data['amount']), data['category'], data['date'], data.get('note', ''))
            )
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "message": "Cleared successfully"}), 201
            
        except Exception as e:
            conn.close()
            return jsonify({"status": "error", "message": str(e)}), 500

    else:
        # GET Request handling structures
        cursor.execute("SELECT type, amount, category, date, note FROM transactions WHERE user_id = ? ORDER BY date DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        transactions = [
            {"type": r[0], "amount": r[1], "category": r[2], "date": r[3], "note": r[4]}
            for r in rows
        ]
        return jsonify(transactions)

# ==========================================
# MULTI-THREADED APP INITIALIZER
# ==========================================

init_db()

# Start Telegram bot only once (preventing worker duplication)
if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
    bot_thread = threading.Thread(
        target=start_telegram_bot,
        daemon=True
    )
    bot_thread.start()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
