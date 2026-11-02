import os
import re
import json
import random
import string
import sqlite3
import docx
import PyPDF2
from PIL import Image
import pytesseract
import torch
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename

# Ensure offline huggingface mode if network is restricted
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from sentence_transformers import SentenceTransformer, util
from db_manager import db_manager
from sign_language_engine import sign_engine
from resume_parser import (
    analyze_resume_full,
    extract_skills_from_text,
    extract_name,
    extract_email,
    extract_phone
)

# Optional translation
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

# Configure Tesseract OCR path
tesseract_paths = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\AppData\Local\Tesseract-OCR\tesseract.exe"
]
for p in tesseract_paths:
    if os.path.exists(p):
        pytesseract.pytesseract.tesseract_cmd = p
        break

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load SBERT model once globally
print("[Model] Loading SentenceTransformer 'all-MiniLM-L6-v2'...")
sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
print("[Model] Loaded successfully!")

# In-memory embedding cache for lightning fast responses
JOB_EMBEDDINGS_CACHE = {}     # job_id -> tensor embedding
RESUME_EMBEDDINGS_CACHE = {}  # resume_id -> tensor embedding

# --- Text Extraction & Helper Functions ---

def translate_if_needed(text):
    if not text or not text.strip() or not HAS_TRANSLATOR:
        return text
    try:
        if any(ord(char) > 127 for char in text[:200]):
            translated = GoogleTranslator(source='auto', target='en').translate(text[:2000])
            return translated if translated else text
    except Exception:
        pass
    return text

def extract_text_from_file(filepath, filename):
    text = ""
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext == ".pdf":
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif ext == ".docx":
            doc = docx.Document(filepath)
            text = " ".join([para.text for para in doc.paragraphs if para.text])
        elif ext in [".txt", ".csv"]:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
            try:
                with Image.open(filepath) as img:
                    text = pytesseract.image_to_string(img)
            except Exception as ocr_err:
                print(f"[OCR] pytesseract notice: {ocr_err}")
                text = f"Image file uploaded: {filename}. OCR processing requires local Tesseract binary."
    except Exception as e:
        print(f"[Extraction] Error reading {filename}: {e}")
    return text.strip()

def get_job_embedding(job_id, job_clean_text):
    if job_id in JOB_EMBEDDINGS_CACHE:
        return JOB_EMBEDDINGS_CACHE[job_id]
    emb = sbert_model.encode(job_clean_text[:2000], convert_to_tensor=True)
    JOB_EMBEDDINGS_CACHE[job_id] = emb
    return emb

def get_resume_embedding(resume_id, resume_clean_text):
    if resume_id in RESUME_EMBEDDINGS_CACHE:
        return RESUME_EMBEDDINGS_CACHE[resume_id]
    emb = sbert_model.encode(resume_clean_text[:2000], convert_to_tensor=True)
    RESUME_EMBEDDINGS_CACHE[resume_id] = emb
    return emb

def extract_job_title(job_text, filename=""):
    lines = [line.strip() for line in job_text.strip().split("\n") if line.strip()]
    if lines and len(lines[0]) < 80 and not lines[0].lower().startswith("job description"):
        return lines[0]
    if filename:
        clean_name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
        return clean_name.title()
    return "Job Opening"

# --- Frontend View Routes ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/matches')
@app.route('/view_matches')
def view_matches():
    keyword = request.args.get("q", "").strip()
    min_score = request.args.get("min_score", "0").strip()
    try:
        min_score_val = float(min_score)
    except ValueError:
        min_score_val = 0.0

    conn = db_manager.get_connection()
    cursor = conn.cursor()

    if db_manager.db_type == "mysql":
        base_query = """
            SELECT m.id, m.score, m.matched_skills, m.missing_skills, m.created_at,
                   r.id AS resume_id, r.candidate_name, r.email, r.text AS resume_text,
                   j.id AS job_id, j.title AS job_title, j.company, j.location
            FROM matches m
            JOIN resumes r ON m.resume_id = r.id
            JOIN jobs j ON m.job_id = j.id
        """
        conditions = []
        params = []
        if keyword:
            conditions.append("(r.candidate_name LIKE %s OR r.text LIKE %s OR j.title LIKE %s OR j.company LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw, kw])
        if min_score_val > 0:
            conditions.append("m.score >= %s")
            params.append(min_score_val)

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        base_query += " ORDER BY m.id DESC LIMIT 100"
        cursor.execute(base_query, params)
    else:
        base_query = """
            SELECT m.id, m.score, m.matched_skills, m.missing_skills, m.created_at,
                   r.id AS resume_id, r.candidate_name, r.email, r.text AS resume_text,
                   j.id AS job_id, j.title AS job_title, j.company, j.location
            FROM matches m
            JOIN resumes r ON m.resume_id = r.id
            JOIN jobs j ON m.job_id = j.id
        """
        conditions = []
        params = []
        if keyword:
            conditions.append("(r.candidate_name LIKE ? OR r.text LIKE ? OR j.title LIKE ? OR j.company LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw, kw])
        if min_score_val > 0:
            conditions.append("m.score >= ?")
            params.append(min_score_val)

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        base_query += " ORDER BY m.id DESC LIMIT 100"
        cursor.execute(base_query, params)

    rows = cursor.fetchall()
    results = []
    for row in rows:
        if isinstance(row, dict) or hasattr(row, 'keys'):
            r = dict(row)
        else:
            r = {
                "id": row[0], "score": row[1], "matched_skills": row[2],
                "missing_skills": row[3], "created_at": row[4],
                "resume_id": row[5], "candidate_name": row[6], "email": row[7],
                "resume_text": row[8], "job_id": row[9], "job_title": row[10],
                "company": row[11], "location": row[12]
            }
        results.append(r)

    cursor.close()
    conn.close()
    return render_template('matches.html', results=results, keyword=keyword, min_score=min_score)

def generate_meet_code():
    part1 = ''.join(random.choices(string.ascii_lowercase, k=3))
    part2 = ''.join(random.choices(string.ascii_lowercase, k=4))
    part3 = ''.join(random.choices(string.ascii_lowercase, k=3))
    return f"{part1}-{part2}-{part3}"

@app.route('/interview', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/interview/<int:interview_id>', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/schedule_interview', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/schedule_interview/<int:interview_id>', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/schedule-interview', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/schedule', methods=['GET', 'POST'], strict_slashes=False)
def interview_session(interview_id=None):
    # Support both GET query parameters and POST form values
    candidate_name = (request.values.get("candidate") or request.values.get("candidate_name") or "").strip()
    job_title = (request.values.get("role") or request.values.get("job_title") or "").strip()
    company = request.values.get("company", "").strip()
    custom_url = request.values.get("meet_url", "").strip()
    score = request.values.get("score", "").strip()

    conn = db_manager.get_connection()
    cursor = conn.cursor()

    # Load all scheduled interviews
    cursor.execute("SELECT id, candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes FROM interviews ORDER BY id DESC")
    rows = cursor.fetchall()

    all_interviews = []
    for r in rows:
        if isinstance(r, dict) or hasattr(r, 'keys'):
            all_interviews.append(dict(r))
        else:
            all_interviews.append({
                "id": r[0], "candidate_name": r[1], "candidate_email": r[2],
                "job_title": r[3], "company": r[4], "interviewer_name": r[5],
                "scheduled_time": r[6], "meet_code": r[7], "meet_url": r[8],
                "status": r[9], "notes": r[10]
            })

    current_session = None
    if interview_id:
        for itw in all_interviews:
            if itw["id"] == interview_id:
                current_session = itw
                break

    if not current_session and (candidate_name or job_title):
        # Create an ad-hoc session from query or form params
        code = generate_meet_code()
        current_session = {
            "id": None,
            "candidate_name": candidate_name or "Candidate",
            "candidate_email": request.values.get("email", "candidate@example.com"),
            "job_title": job_title or "Software Engineer",
            "company": company or "TalentAI Partner",
            "interviewer_name": "Senior Technical Panel",
            "scheduled_time": "Now (Live Screening)",
            "meet_code": code,
            "meet_url": custom_url or f"https://meet.google.com/new",
            "status": "Ready to Join",
            "notes": "Direct technical screening interview session.",
            "score": score
        }

    if not current_session:
        if all_interviews:
            current_session = all_interviews[0]
        else:
            code = generate_meet_code()
            current_session = {
                "id": None,
                "candidate_name": "Alex Johnson",
                "candidate_email": "alex.johnson@example.com",
                "job_title": "Senior Machine Learning Engineer",
                "company": "Nuna AI",
                "interviewer_name": "Dr. Emily Chen (Lead AI Scientist)",
                "scheduled_time": "Today, 3:30 PM (IST)",
                "meet_code": code,
                "meet_url": "https://meet.google.com/new",
                "status": "Ready to Join",
                "notes": "Round 2: System Architecture & Deep Learning Coding.",
                "score": "64.2"
            }
    elif score and "score" not in current_session:
        current_session["score"] = score

    cursor.close()
    conn.close()

    return render_template(
        'interview.html',
        session=current_session,
        all_interviews=all_interviews
    )

@app.route('/accessible-interview', methods=['GET', 'POST'], strict_slashes=False)
@app.route('/accessible-interview/<int:interview_id>', methods=['GET', 'POST'], strict_slashes=False)
def accessible_interview(interview_id=None):
    """
    Accessible Interview Suite specifically designed for deaf and mute candidates:
    - Real-time vision-based sign language recognition (MediaPipe 21 landmarks)
    - Two-way assistive communication:
        * Sign-to-Text & Sign-to-Speech (reads signs out loud for interviewer)
        * Speech-to-Text Closed Captions (transcribes interviewer's speech for candidate)
    """
    candidate_name = (request.values.get("candidate") or request.values.get("candidate_name") or "").strip()
    job_title = (request.values.get("role") or request.values.get("job_title") or "").strip()
    company = request.values.get("company", "").strip()
    score = request.values.get("score", "").strip()

    conn = db_manager.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes FROM interviews ORDER BY id DESC")
    rows = cursor.fetchall()
    all_interviews = []
    for r in rows:
        if isinstance(r, dict) or hasattr(r, 'keys'):
            all_interviews.append(dict(r))
        else:
            all_interviews.append({
                "id": r[0], "candidate_name": r[1], "candidate_email": r[2],
                "job_title": r[3], "company": r[4], "interviewer_name": r[5],
                "scheduled_time": r[6], "meet_code": r[7], "meet_url": r[8],
                "status": r[9], "notes": r[10]
            })

    current_session = None
    if interview_id:
        for itw in all_interviews:
            if itw["id"] == interview_id:
                current_session = itw
                break

    if not current_session and (candidate_name or job_title):
        code = generate_meet_code()
        current_session = {
            "id": None,
            "candidate_name": candidate_name or "Candidate",
            "candidate_email": request.values.get("email", "candidate@example.com"),
            "job_title": job_title or "Software Engineer",
            "company": company or "TalentAI Partner",
            "interviewer_name": "Senior Technical Panel",
            "scheduled_time": "Now (Live Screening)",
            "meet_code": code,
            "meet_url": f"https://meet.google.com/new",
            "status": "Accessible Room Active",
            "notes": "Sign-Language Assisted Interview Session for Deaf/Mute Inclusivity.",
            "score": score
        }

    if not current_session:
        if all_interviews:
            current_session = all_interviews[0]
        else:
            code = generate_meet_code()
            current_session = {
                "id": None,
                "candidate_name": "Alex Johnson (Deaf/Mute Candidate)",
                "candidate_email": "alex.johnson@example.com",
                "job_title": "Senior Machine Learning Engineer",
                "company": "Nuna AI",
                "interviewer_name": "Dr. Emily Chen (Lead AI Scientist)",
                "scheduled_time": "Today, 3:30 PM (IST)",
                "meet_code": code,
                "meet_url": "https://meet.google.com/new",
                "status": "Accessible Room Active",
                "notes": "Assistive Sign Language Recognition Enabled.",
                "score": "64.2"
            }
    elif score and "score" not in current_session:
        current_session["score"] = score

    cursor.close()
    conn.close()

    return render_template(
        'accessible_interview.html',
        session=current_session,
        all_interviews=all_interviews
    )

@app.route('/api/recognize_gesture', methods=['POST'])
def api_recognize_gesture():
    """
    Backend gesture recognition endpoint that accepts 21 normalized landmarks
    and returns classified gesture, confidence, and meaning.
    """
    data = request.get_json(silent=True) or {}
    landmarks = data.get('landmarks', [])
    if not landmarks or len(landmarks) < 21:
        return jsonify({"error": "Valid 21 hand landmarks required"}), 400

    result = sign_engine.classify_gesture(landmarks)
    return jsonify({
        "success": True,
        "sign": result.get("sign", ""),
        "type": result.get("type", "none"),
        "description": result.get("description", ""),
        "confidence": result.get("confidence", 0.0)
    })

@app.route('/api/interviews', methods=['GET', 'POST'])
def manage_interviews():
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    if request.method == 'GET':
        cursor.execute("SELECT id, candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes FROM interviews ORDER BY id DESC")
        rows = cursor.fetchall()
        interviews = []
        for r in rows:
            if isinstance(r, dict) or hasattr(r, 'keys'):
                interviews.append(dict(r))
            else:
                interviews.append({
                    "id": r[0], "candidate_name": r[1], "candidate_email": r[2],
                    "job_title": r[3], "company": r[4], "interviewer_name": r[5],
                    "scheduled_time": r[6], "meet_code": r[7], "meet_url": r[8],
                    "status": r[9], "notes": r[10]
                })
        cursor.close()
        conn.close()
        return jsonify({"interviews": interviews})

    # POST: create new interview
    data = request.get_json(silent=True) or request.form
    candidate_name = data.get('candidate_name', '').strip()
    job_title = data.get('job_title', '').strip()

    if not candidate_name or not job_title:
        cursor.close()
        conn.close()
        return jsonify({"error": "Candidate name and job title are required"}), 400

    candidate_email = data.get('candidate_email', '').strip() or f"{candidate_name.lower().replace(' ', '')}@example.com"
    company = data.get('company', '').strip() or "TalentAI Partner"
    interviewer_name = data.get('interviewer_name', '').strip() or "Senior Technical Panel"
    scheduled_time = data.get('scheduled_time', '').strip() or "Today, Next Slot"
    meet_code = data.get('meet_code', '').strip() or generate_meet_code()
    meet_url = data.get('meet_url', '').strip() or "https://meet.google.com/new"
    status = data.get('status', '').strip() or "Scheduled"
    notes = data.get('notes', '').strip() or "Technical Interview Assessment"

    if db_manager.db_type == "mysql":
        cursor.execute("""
            INSERT INTO interviews 
            (candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes))
    else:
        cursor.execute("""
            INSERT INTO interviews 
            (candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes))

    new_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "interview_id": new_id,
        "candidate_name": candidate_name,
        "meet_url": meet_url,
        "meet_code": meet_code
    })

@app.route('/api/interviews/<int:interview_id>/delete', methods=['POST'])
def delete_interview(interview_id):
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    if db_manager.db_type == "mysql":
        cursor.execute("DELETE FROM interviews WHERE id=%s", (interview_id,))
    else:
        cursor.execute("DELETE FROM interviews WHERE id=?", (interview_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True, "deleted_id": interview_id})

# --- REST APIs for Interactive Dashboard ---

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM resumes")
    total_resumes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*), AVG(score) FROM matches")
    row = cursor.fetchone()
    total_matches = row[0] or 0
    avg_score = round(row[1], 1) if row[1] else 0.0

    cursor.close()
    conn.close()

    return jsonify({
        "total_resumes": total_resumes,
        "total_jobs": total_jobs,
        "total_matches": total_matches,
        "avg_score": avg_score
    })

@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    search = request.args.get('search', '').strip()
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    query = "SELECT id, title, company, location, description FROM jobs"
    params = []
    if search:
        if db_manager.db_type == "mysql":
            query += " WHERE title LIKE %s OR company LIKE %s OR description LIKE %s"
        else:
            query += " WHERE title LIKE ? OR company LIKE ? OR description LIKE ?"
        kw = f"%{search}%"
        params = [kw, kw, kw]

    query += " ORDER BY id DESC LIMIT 50"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    jobs = []
    for r in rows:
        jobs.append({
            "id": r[0] if isinstance(r, (tuple, list)) else r["id"],
            "title": r[1] if isinstance(r, (tuple, list)) else r["title"],
            "company": r[2] if isinstance(r, (tuple, list)) else r["company"],
            "location": r[3] if isinstance(r, (tuple, list)) else r["location"],
            "preview": (r[4] if isinstance(r, (tuple, list)) else r["description"])[:200] + "..."
        })
    cursor.close()
    conn.close()
    return jsonify({"jobs": jobs})

@app.route('/api/add_job', methods=['POST'])
def add_job():
    data = request.get_json() or request.form
    title = data.get('title', '').strip()
    company = data.get('company', '').strip()
    location = data.get('location', '').strip()
    description = data.get('description', '').strip()

    if not title or not description:
        return jsonify({"error": "Title and Description are required"}), 400

    clean_desc = description.lower().strip()
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    if db_manager.db_type == "mysql":
        cursor.execute(
            "INSERT INTO jobs (title, company, location, description, clean_desc) VALUES (%s, %s, %s, %s, %s)",
            (title, company, location, description, clean_desc)
        )
    else:
        cursor.execute(
            "INSERT INTO jobs (title, company, location, description, clean_desc) VALUES (?, ?, ?, ?, ?)",
            (title, company, location, description, clean_desc)
        )
    job_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    # Pre-cache job embedding
    get_job_embedding(job_id, clean_desc)

    return jsonify({"success": True, "job_id": job_id, "title": title})

@app.route('/api/match_resume', methods=['POST'])
def match_resume():
    """
    Unified endpoint for matching a resume (file upload or pasted text).
    Optimized with batched semantic similarity & caching.
    """
    resume_text = ""
    filename = ""

    if 'resume_file' in request.files and request.files['resume_file'].filename != '':
        file = request.files['resume_file']
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        resume_text = extract_text_from_file(filepath, filename)
    elif 'resume_text' in request.form and request.form['resume_text'].strip():
        resume_text = request.form['resume_text'].strip()
    elif request.is_json and request.json.get('resume_text'):
        resume_text = request.json.get('resume_text').strip()

    if not resume_text:
        return jsonify({"error": "No resume text or valid file provided"}), 400

    resume_text = translate_if_needed(resume_text)
    clean_resume = resume_text.lower().strip()

    # Parse candidate profile details
    parsed = analyze_resume_full(resume_text)
    skills_str = ", ".join(parsed["skills"])
    resume_skills_set = set(s.lower() for s in parsed["skills"])

    # Save to database
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    if db_manager.db_type == "mysql":
        cursor.execute(
            "INSERT INTO resumes (candidate_name, email, phone, text, clean_resume, skills) VALUES (%s, %s, %s, %s, %s, %s)",
            (parsed["name"], parsed["email"], parsed["phone"], resume_text, clean_resume, skills_str)
        )
    else:
        cursor.execute(
            "INSERT INTO resumes (candidate_name, email, phone, text, clean_resume, skills) VALUES (?, ?, ?, ?, ?, ?)",
            (parsed["name"], parsed["email"], parsed["phone"], resume_text, clean_resume, skills_str)
        )
    resume_id = cursor.lastrowid
    conn.commit()

    # Encode resume ONCE
    resume_emb = sbert_model.encode(clean_resume[:2000], convert_to_tensor=True)
    RESUME_EMBEDDINGS_CACHE[resume_id] = resume_emb

    # Retrieve all jobs
    cursor.execute("SELECT id, title, company, location, description, clean_desc FROM jobs")
    jobs = cursor.fetchall()

    if not jobs:
        cursor.close()
        conn.close()
        return jsonify({
            "success": True,
            "resume_id": resume_id,
            "candidate": parsed,
            "top_matches": [],
            "total_jobs_evaluated": 0
        })

    # Prepare job embeddings (collect cached or batch-encode uncached)
    job_ids = []
    job_embs_list = []
    uncached_indices = []
    uncached_texts = []

    for i, job in enumerate(jobs):
        j_id = job[0] if isinstance(job, (tuple, list)) else job["id"]
        j_clean = job[5] if isinstance(job, (tuple, list)) else job["clean_desc"]
        job_ids.append(j_id)

        if j_id in JOB_EMBEDDINGS_CACHE:
            job_embs_list.append(JOB_EMBEDDINGS_CACHE[j_id])
        else:
            uncached_indices.append(i)
            uncached_texts.append(j_clean[:2000])
            job_embs_list.append(None)

    # Batch encode any uncached jobs in one fast tensor operation
    if uncached_texts:
        new_embs = sbert_model.encode(uncached_texts, batch_size=32, convert_to_tensor=True, show_progress_bar=False)
        for idx, new_emb in zip(uncached_indices, new_embs):
            JOB_EMBEDDINGS_CACHE[job_ids[idx]] = new_emb
            job_embs_list[idx] = new_emb

    # Compute all cosine similarities in a single matrix multiplication
    stacked_job_embs = torch.stack(job_embs_list)
    cosine_sims = util.cos_sim(resume_emb, stacked_job_embs)[0].tolist()

    # Assemble match results with skill analysis
    match_results = []
    matches_to_insert = []

    for i, job in enumerate(jobs):
        j_id = job[0] if isinstance(job, (tuple, list)) else job["id"]
        j_title = job[1] if isinstance(job, (tuple, list)) else job["title"]
        j_comp = job[2] if isinstance(job, (tuple, list)) else job["company"]
        j_loc = job[3] if isinstance(job, (tuple, list)) else job["location"]
        j_desc = job[4] if isinstance(job, (tuple, list)) else job["description"]
        j_clean = job[5] if isinstance(job, (tuple, list)) else job["clean_desc"]

        raw_sbert = max(0.0, min(1.0, float(cosine_sims[i])))

        # Skill match
        job_skills_list = extract_skills_from_text(j_clean)
        job_skills = set(s.lower() for s in job_skills_list)
        matched_skills = [s for s in job_skills_list if s.lower() in resume_skills_set]
        missing_skills = [s for s in job_skills_list if s.lower() not in resume_skills_set]

        if job_skills:
            skill_score = len(matched_skills) / len(job_skills)
        else:
            skill_score = raw_sbert

        composite = (0.65 * raw_sbert) + (0.35 * skill_score)
        composite_pct = round(composite * 100, 1)

        matched_str = ", ".join(matched_skills)
        missing_str = ", ".join(missing_skills)
        matches_to_insert.append((j_id, resume_id, composite_pct, matched_str, missing_str))

        match_results.append({
            "job_id": j_id,
            "job_title": j_title,
            "company": j_comp or "Top Employer",
            "location": j_loc or "Remote / Hybrid",
            "score": composite_pct,
            "sbert_score": round(raw_sbert * 100, 1),
            "skill_score": round(skill_score * 100, 1),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "preview": j_desc[:180] + "..."
        })

    # Bulk insert matches
    if db_manager.db_type == "mysql":
        cursor.executemany(
            "INSERT INTO matches (job_id, resume_id, score, matched_skills, missing_skills) VALUES (%s, %s, %s, %s, %s)",
            matches_to_insert
        )
    else:
        cursor.executemany(
            "INSERT INTO matches (job_id, resume_id, score, matched_skills, missing_skills) VALUES (?, ?, ?, ?, ?)",
            matches_to_insert
        )

    conn.commit()
    cursor.close()
    conn.close()

    match_results.sort(key=lambda x: x["score"], reverse=True)
    top_matches = match_results[:6]

    return jsonify({
        "success": True,
        "resume_id": resume_id,
        "candidate": parsed,
        "top_matches": top_matches,
        "total_jobs_evaluated": len(jobs)
    })

@app.route('/api/match_job', methods=['POST'])
def match_job():
    """
    Recruiter endpoint: paste or upload a job description -> find top candidate resumes.
    Optimized with batched semantic similarity & caching.
    """
    job_text = ""
    filename = ""

    if 'job_file' in request.files and request.files['job_file'].filename != '':
        file = request.files['job_file']
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        job_text = extract_text_from_file(filepath, filename)
    elif 'job_text' in request.form and request.form['job_text'].strip():
        job_text = request.form['job_text'].strip()
    elif request.is_json and request.json.get('job_text'):
        job_text = request.json.get('job_text').strip()

    if not job_text:
        return jsonify({"error": "No job description provided"}), 400

    job_text = translate_if_needed(job_text)
    clean_job = job_text.lower().strip()
    job_title = extract_job_title(job_text, filename)

    # Save job to DB
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    if db_manager.db_type == "mysql":
        cursor.execute(
            "INSERT INTO jobs (title, description, clean_desc) VALUES (%s, %s, %s)",
            (job_title, job_text, clean_job)
        )
    else:
        cursor.execute(
            "INSERT INTO jobs (title, description, clean_desc) VALUES (?, ?, ?)",
            (job_title, job_text, clean_job)
        )
    job_id = cursor.lastrowid
    conn.commit()

    # Encode job ONCE
    job_emb = sbert_model.encode(clean_job[:2000], convert_to_tensor=True)
    JOB_EMBEDDINGS_CACHE[job_id] = job_emb

    # Retrieve all candidate resumes
    cursor.execute("SELECT id, candidate_name, email, text, clean_resume, skills FROM resumes")
    resumes = cursor.fetchall()

    if not resumes:
        cursor.close()
        conn.close()
        return jsonify({
            "success": True,
            "job_id": job_id,
            "job_title": job_title,
            "top_candidates": [],
            "total_candidates_evaluated": 0
        })

    # Prepare candidate embeddings
    resume_ids = []
    res_embs_list = []
    uncached_indices = []
    uncached_texts = []

    for i, res in enumerate(resumes):
        r_id = res[0] if isinstance(res, (tuple, list)) else res["id"]
        r_clean = res[4] if isinstance(res, (tuple, list)) else res["clean_resume"]
        resume_ids.append(r_id)

        if r_id in RESUME_EMBEDDINGS_CACHE:
            res_embs_list.append(RESUME_EMBEDDINGS_CACHE[r_id])
        else:
            uncached_indices.append(i)
            uncached_texts.append(r_clean[:2000])
            res_embs_list.append(None)

    if uncached_texts:
        new_embs = sbert_model.encode(uncached_texts, batch_size=32, convert_to_tensor=True, show_progress_bar=False)
        for idx, new_emb in zip(uncached_indices, new_embs):
            RESUME_EMBEDDINGS_CACHE[resume_ids[idx]] = new_emb
            res_embs_list[idx] = new_emb

    # Batched cosine similarity
    stacked_res_embs = torch.stack(res_embs_list)
    cosine_sims = util.cos_sim(job_emb, stacked_res_embs)[0].tolist()

    job_skills_list = extract_skills_from_text(clean_job)
    job_skills = set(s.lower() for s in job_skills_list)

    candidate_matches = []
    matches_to_insert = []

    for i, res in enumerate(resumes):
        r_id = res[0] if isinstance(res, (tuple, list)) else res["id"]
        r_name = res[1] if isinstance(res, (tuple, list)) else res["candidate_name"]
        r_email = res[2] if isinstance(res, (tuple, list)) else res["email"]
        r_text = res[3] if isinstance(res, (tuple, list)) else res["text"]
        r_clean = res[4] if isinstance(res, (tuple, list)) else res["clean_resume"]

        raw_sbert = max(0.0, min(1.0, float(cosine_sims[i])))

        # Skill match
        resume_skills_set = set(s.lower() for s in extract_skills_from_text(r_clean))
        matched_skills = [s for s in job_skills_list if s.lower() in resume_skills_set]
        missing_skills = [s for s in job_skills_list if s.lower() not in resume_skills_set]

        if job_skills:
            skill_score = len(matched_skills) / len(job_skills)
        else:
            skill_score = raw_sbert

        composite = (0.65 * raw_sbert) + (0.35 * skill_score)
        composite_pct = round(composite * 100, 1)

        matched_str = ", ".join(matched_skills)
        missing_str = ", ".join(missing_skills)
        matches_to_insert.append((job_id, r_id, composite_pct, matched_str, missing_str))

        candidate_matches.append({
            "resume_id": r_id,
            "candidate_name": r_name or f"Candidate #{r_id}",
            "email": r_email or "Not provided",
            "score": composite_pct,
            "sbert_score": round(raw_sbert * 100, 1),
            "skill_score": round(skill_score * 100, 1),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "preview": r_text[:180] + "..."
        })

    # Bulk insert matches
    if db_manager.db_type == "mysql":
        cursor.executemany(
            "INSERT INTO matches (job_id, resume_id, score, matched_skills, missing_skills) VALUES (%s, %s, %s, %s, %s)",
            matches_to_insert
        )
    else:
        cursor.executemany(
            "INSERT INTO matches (job_id, resume_id, score, matched_skills, missing_skills) VALUES (?, ?, ?, ?, ?)",
            matches_to_insert
        )

    conn.commit()
    cursor.close()
    conn.close()

    candidate_matches.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = candidate_matches[:6]

    return jsonify({
        "success": True,
        "job_id": job_id,
        "job_title": job_title,
        "top_candidates": top_candidates,
        "total_candidates_evaluated": len(resumes)
    })

# --- Backward Compatible Form Routes ---

@app.route('/upload_resume', methods=['POST'])
def upload_resume_legacy():
    return match_resume()

@app.route('/upload_resume_file', methods=['POST'])
def upload_resume_file_legacy():
    return match_resume()

@app.route('/upload_job_file', methods=['POST'])
def upload_job_file_legacy():
    return match_job()

@app.route('/match', methods=['POST'])
def match_by_job_id_legacy():
    data = request.get_json(silent=True) or request.form
    job_id = data.get('job_id')
    if not job_id:
        return jsonify({"error": "No job ID provided"}), 400

    conn = db_manager.get_connection()
    cursor = conn.cursor()

    if db_manager.db_type == "mysql":
        cursor.execute("SELECT id, title, description, clean_desc FROM jobs WHERE id=%s", (job_id,))
    else:
        cursor.execute("SELECT id, title, description, clean_desc FROM jobs WHERE id=?", (job_id,))
    job = cursor.fetchone()

    if not job:
        cursor.close()
        conn.close()
        return jsonify({"error": f"Job with ID {job_id} not found"}), 404

    j_id = job[0] if isinstance(job, (tuple, list)) else job["id"]
    j_title = job[1] if isinstance(job, (tuple, list)) else job["title"]
    j_clean = job[3] if isinstance(job, (tuple, list)) else job["clean_desc"]

    job_emb = get_job_embedding(j_id, j_clean)

    cursor.execute("SELECT id, candidate_name, email, text, clean_resume, skills FROM resumes")
    resumes = cursor.fetchall()

    if not resumes:
        cursor.close()
        conn.close()
        return jsonify({"success": True, "job_title": j_title, "top_matches": []})

    resume_ids = []
    res_embs_list = []
    uncached_indices = []
    uncached_texts = []

    for i, res in enumerate(resumes):
        r_id = res[0] if isinstance(res, (tuple, list)) else res["id"]
        r_clean = res[4] if isinstance(res, (tuple, list)) else res["clean_resume"]
        resume_ids.append(r_id)

        if r_id in RESUME_EMBEDDINGS_CACHE:
            res_embs_list.append(RESUME_EMBEDDINGS_CACHE[r_id])
        else:
            uncached_indices.append(i)
            uncached_texts.append(r_clean[:2000])
            res_embs_list.append(None)

    if uncached_texts:
        new_embs = sbert_model.encode(uncached_texts, batch_size=32, convert_to_tensor=True, show_progress_bar=False)
        for idx, new_emb in zip(uncached_indices, new_embs):
            RESUME_EMBEDDINGS_CACHE[resume_ids[idx]] = new_emb
            res_embs_list[idx] = new_emb

    stacked_res_embs = torch.stack(res_embs_list)
    cosine_sims = util.cos_sim(job_emb, stacked_res_embs)[0].tolist()

    job_skills_list = extract_skills_from_text(j_clean)
    matches = []

    for i, r in enumerate(resumes):
        r_id = r[0] if isinstance(r, (tuple, list)) else r["id"]
        r_name = r[1] if isinstance(r, (tuple, list)) else r["candidate_name"]
        r_email = r[2] if isinstance(r, (tuple, list)) else r["email"]
        r_text = r[3] if isinstance(r, (tuple, list)) else r["text"]
        r_clean = r[4] if isinstance(r, (tuple, list)) else r["clean_resume"]

        raw_sbert = max(0.0, min(1.0, float(cosine_sims[i])))
        resume_skills_set = set(s.lower() for s in extract_skills_from_text(r_clean))
        matched_skills = [s for s in job_skills_list if s.lower() in resume_skills_set]
        missing_skills = [s for s in job_skills_list if s.lower() not in resume_skills_set]

        if job_skills_list:
            skill_score = len(matched_skills) / len(job_skills_list)
        else:
            skill_score = raw_sbert

        composite = (0.65 * raw_sbert) + (0.35 * skill_score)
        composite_pct = round(composite * 100, 1)

        matches.append({
            "resume_id": r_id,
            "candidate_name": r_name,
            "email": r_email,
            "score": composite_pct,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "preview": r_text[:180] + "..."
        })

    cursor.close()
    conn.close()

    matches.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({
        "success": True,
        "job_title": j_title,
        "top_matches": matches[:6]
    })

# --- Run Application ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n=======================================================")
    print(f" AI Resume-Job Matching System Running at:")
    print(f" http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=True)
