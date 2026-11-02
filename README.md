# ⚡ TalentAI — Semantic Resume & Job Matching System

An AI-powered Applicant Tracking & Matchmaking System (ATS) that semantically matches candidate resumes with job descriptions using **Sentence-BERT (`all-MiniLM-L6-v2`)** and taxonomy-driven skill gap analysis.

---

## 🌟 Key Highlights & Features

1. **🧠 Dense Semantic Embedding Matching (Sentence-BERT)**
   - Utilizes Hugging Face's `all-MiniLM-L6-v2` transformer model to compute deep contextual cosine similarity.
   - Goes beyond naive keyword matching: understands that *"Building REST APIs in Django"* aligns closely with *"Python Web Backend Engineering"*.
   - **Tensor-batched matrix calculations** with in-memory caching for sub-100ms response times.

2. **📊 Hybrid Scoring & Skill Gap Analysis**
   - **Composite Fit Score**: 65% Semantic SBERT Context + 35% Hard Technical Skill Overlap.
   - Highlights **Matched Skills** (qualifications the candidate possesses).
   - Identifies **Skill Gaps** (key job requirements the candidate is missing).

3. **📄 Multi-Format Resume Ingestion**
   - Supports **PDF** (`PyPDF2`), **Word DOCX** (`python-docx`), and plain text.
   - Built-in OCR pipeline for image resumes (`pytesseract` + `Pillow`).
   - Integrated multilingual translation support (`deep-translator`).

4. **💾 Dual-Engine Database (Zero-Config)**
   - **SQLite** (Default): Embedded, zero-setup, auto-seeds 30 real job postings and 20 sample candidate profiles on first launch.
   - **MySQL** (Production/Course Requirement): Seamlessly switches to MySQL when configured via environment variables.

5. **📹 Google Meet Interview Session & Lobby**
   - **Pre-Call Audio/Video Check**: Interactive camera preview and microphone check using browser WebRTC (with fallback avatar).
   - **Direct Join Gateway**: Direction steps and a prominent 1-click **"Join Google Meet Call Now ↗"** button that opens a real Google Meet room (`https://meet.google.com/new` or custom room code).
   - **Custom Room Override & Copy Link**: Supports copying invite links or entering specific meeting URLs.
   - **Interactive Meeting Simulator**: Embedded call demonstration mode for project presentations.
   - **Session Scheduler**: Easily create interview sessions for candidates matched in the dashboard.

6. **🎨 Modern Interactive Dashboard**
   - **Candidate Portal**: Drag & drop resume file or paste text to receive instant job recommendations with match percentages and 1-click interview scheduling.
   - **Recruiter Portal**: Match candidate resumes against new job descriptions or active openings.
   - **Job Openings Catalog**: Search and browse indexed positions.
   - **Analytics & History**: Filter matches by candidate, role, company, and minimum score threshold.

---

## 🏗️ System Architecture

```text
[ Resume File / Text ]               [ Job Description ]
 (PDF, DOCX, TXT, OCR)                      |
           |                                |
           v                                v
  [ Resume Parser ]                 [ Job Extractor ]
  - Name, Email, Phone              - Title, Requirements
  - Skills Taxonomy Match           - Technical Skills
           |                                |
           +----------------+---------------+
                            |
                            v
              [ Sentence-BERT (MiniLM-L6) ]
               + Cosine Similarity Matrix
               + Skill Gap Overlap Engine
                            |
                            v
       [ Hybrid Match Score & Skill Breakdown ]
      (e.g., 88.5% Fit | Matched vs Missing Skills)
                            |
                            v
       [ SQLite / MySQL Storage & Web Dashboard ]
```

---

## 📁 Project Structure

```
mini project/
│── app.py                   # Main Flask Application & API Endpoints
│── db_manager.py            # SQLite & MySQL Database Manager & Auto-seeder
│── resume_parser.py         # Heuristic & Regex Parser for Contact, Skills & Education
│── mini_project.py          # TF-IDF & NLTK Machine Learning Demo / Heatmap Script
│── test_match.py            # Standalone SBERT similarity demonstration script
│── test_server_endpoints.py # Automated test suite for Flask endpoints
│── requirements.txt         # Python dependencies
│── glassdoor_jobs.csv       # Job dataset (Glassdoor postings)
│── resume_data.csv          # Resume dataset
│── templates/
│   ├── index.html           # Main dashboard UI
│   └── matches.html         # Historical match records & analytics page
│── static/
│   ├── style.css            # Responsive modern UI styling
│   └── script.js            # Frontend interactivity, drag-and-drop, AJAX requests
└── uploads/                 # Temporary storage for uploaded resumes
```

---

## 🚀 Quick Start Guide

### 1. Activate Environment
Open PowerShell or your terminal in this directory:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Run the Application
```powershell
python app.py
```

### 3. Open in Your Browser
Navigate to:
```
http://127.0.0.1:5000
```

---

## 🧪 Testing & Verification

Run the automated endpoint verification test suite:
```powershell
python test_server_endpoints.py
```

Run the standalone NLP / TF-IDF visualization script:
```powershell
python mini_project.py
```

---

## ⚙️ Configuration (Optional MySQL Mode)

By default, the application runs on SQLite (`resume_matcher.db`) so it works out of the box without any database setup.

To use MySQL instead:
```powershell
$env:USE_MYSQL="1"
$env:MYSQL_HOST="localhost"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="YourPassword"
$env:MYSQL_DB="resume_match_db"
python app.py
```

---

## 📚 Technical Stack
- **Backend**: Python 3, Flask, Werkzeug
- **AI / NLP**: PyTorch, Sentence-Transformers (`all-MiniLM-L6-v2`), Scikit-Learn, NLTK
- **Document Parsing**: PyPDF2, python-docx, Pillow, pytesseract
- **Database**: SQLite3 / MySQL Connector
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3 Glassmorphism
