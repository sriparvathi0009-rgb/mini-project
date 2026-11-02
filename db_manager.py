import os
import sqlite3
import csv
import re
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume_matcher.db")

# Optional MySQL configuration via environment variables
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "Sri2026@PU")
MYSQL_DB = os.environ.get("MYSQL_DB", "resume_match_db")
USE_MYSQL = os.environ.get("USE_MYSQL", "0") == "1"

class DatabaseManager:
    def __init__(self):
        self.db_type = "sqlite"
        self._init_connection()
        self.create_tables()
        self.seed_initial_data()

    def _init_connection(self):
        if USE_MYSQL:
            try:
                import mysql.connector
                conn = mysql.connector.connect(
                    host=MYSQL_HOST,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD
                )
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
                conn.commit()
                cursor.close()
                conn.close()

                # Test connect to DB
                test_conn = mysql.connector.connect(
                    host=MYSQL_HOST,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB
                )
                test_conn.close()
                self.db_type = "mysql"
                print(f"[DB] Connected to MySQL database '{MYSQL_DB}' successfully.")
                return
            except Exception as e:
                print(f"[DB] MySQL connection failed ({e}). Falling back to SQLite.")

        self.db_type = "sqlite"
        print(f"[DB] Using SQLite database at: {DB_FILE}")

    def get_connection(self):
        if self.db_type == "mysql":
            import mysql.connector
            return mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
        else:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            return conn

    def create_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        if self.db_type == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    company VARCHAR(255) DEFAULT '',
                    location VARCHAR(255) DEFAULT '',
                    description TEXT,
                    clean_desc TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    candidate_name VARCHAR(255) DEFAULT '',
                    email VARCHAR(255) DEFAULT '',
                    phone VARCHAR(100) DEFAULT '',
                    text MEDIUMTEXT,
                    clean_resume MEDIUMTEXT,
                    skills TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    job_id INT,
                    resume_id INT,
                    score FLOAT,
                    matched_skills TEXT,
                    missing_skills TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interviews (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    candidate_name VARCHAR(255) NOT NULL,
                    candidate_email VARCHAR(255) DEFAULT '',
                    job_title VARCHAR(255) NOT NULL,
                    company VARCHAR(255) DEFAULT '',
                    interviewer_name VARCHAR(255) DEFAULT 'Technical Interview Panel',
                    scheduled_time VARCHAR(100) DEFAULT '',
                    meet_code VARCHAR(100) DEFAULT '',
                    meet_url TEXT,
                    status VARCHAR(50) DEFAULT 'Scheduled',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    company TEXT DEFAULT '',
                    location TEXT DEFAULT '',
                    description TEXT,
                    clean_desc TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_name TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    text TEXT,
                    clean_resume TEXT,
                    skills TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    resume_id INTEGER,
                    score REAL,
                    matched_skills TEXT,
                    missing_skills TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_name TEXT NOT NULL,
                    candidate_email TEXT DEFAULT '',
                    job_title TEXT NOT NULL,
                    company TEXT DEFAULT '',
                    interviewer_name TEXT DEFAULT 'Technical Interview Panel',
                    scheduled_time TEXT DEFAULT '',
                    meet_code TEXT DEFAULT '',
                    meet_url TEXT DEFAULT '',
                    status TEXT DEFAULT 'Scheduled',
                    notes TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

        conn.commit()
        cursor.close()
        conn.close()

    def seed_initial_data(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check existing jobs count
        cursor.execute("SELECT COUNT(*) FROM jobs")
        job_count = cursor.fetchone()[0]

        if job_count == 0:
            csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glassdoor_jobs.csv")
            if os.path.exists(csv_path):
                print("[DB] Seeding jobs from glassdoor_jobs.csv...")
                seeded = 0
                seen_titles = set()
                try:
                    with open(csv_path, mode="r", encoding="utf-8", errors="ignore") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            title = (row.get("Job Title") or "").strip()
                            desc = (row.get("Job Description") or "").strip()
                            company = (row.get("Company Name") or "").split("\n")[0].strip()
                            location = (row.get("Location") or "").strip()

                            if not title or not desc or len(desc) < 50:
                                continue

                            # Normalize title to get good variety
                            key = title.lower()
                            if key in seen_titles and seeded >= 15:
                                continue
                            seen_titles.add(key)

                            clean = desc.lower().strip()
                            if self.db_type == "mysql":
                                cursor.execute(
                                    "INSERT INTO jobs (title, company, location, description, clean_desc) VALUES (%s, %s, %s, %s, %s)",
                                    (title, company, location, desc, clean)
                                )
                            else:
                                cursor.execute(
                                    "INSERT INTO jobs (title, company, location, description, clean_desc) VALUES (?, ?, ?, ?, ?)",
                                    (title, company, location, desc, clean)
                                )
                            seeded += 1
                            if seeded >= 30:
                                break
                    conn.commit()
                    print(f"[DB] Successfully seeded {seeded} diverse job postings.")
                except Exception as e:
                    print(f"[DB] Warning: Failed to seed jobs from CSV: {e}")

        # Check existing resumes count
        cursor.execute("SELECT COUNT(*) FROM resumes")
        resume_count = cursor.fetchone()[0]

        if resume_count == 0:
            csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume_data.csv")
            if os.path.exists(csv_path):
                print("[DB] Seeding sample candidate resumes from resume_data.csv...")
                seeded = 0
                try:
                    with open(csv_path, mode="r", encoding="utf-8", errors="ignore") as f:
                        reader = csv.DictReader(f)
                        for i, row in enumerate(reader):
                            obj = row.get("career_objective", "") or ""
                            skills_raw = row.get("skills", "") or ""
                            resp = row.get("responsibilities", "") or ""
                            position = row.get("\ufeffjob_position_name", "") or row.get("positions", "") or f"Candidate {i+1}"
                            degree = row.get("degree_names", "") or ""
                            institution = row.get("educational_institution_name", "") or ""

                            # Clean up skills list if it's formatted as string array
                            skills_clean = skills_raw.replace("[", "").replace("]", "").replace("'", "").strip()

                            text = f"Candidate Profile: {position}\nObjective: {obj}\nSkills: {skills_clean}\nEducation: {degree} at {institution}\nExperience & Responsibilities: {resp}"
                            if len(text.strip()) < 50:
                                continue

                            candidate_name = f"Candidate #{seeded+1} ({position})"
                            clean = text.lower().strip()

                            if self.db_type == "mysql":
                                cursor.execute(
                                    "INSERT INTO resumes (candidate_name, email, phone, text, clean_resume, skills) VALUES (%s, %s, %s, %s, %s, %s)",
                                    (candidate_name, f"candidate{seeded+1}@example.com", "+1-555-0199", text, clean, skills_clean)
                                )
                            else:
                                cursor.execute(
                                    "INSERT INTO resumes (candidate_name, email, phone, text, clean_resume, skills) VALUES (?, ?, ?, ?, ?, ?)",
                                    (candidate_name, f"candidate{seeded+1}@example.com", "+1-555-0199", text, clean, skills_clean)
                                )
                            seeded += 1
                            if seeded >= 20:
                                break
                    conn.commit()
                    print(f"[DB] Successfully seeded {seeded} candidate resumes.")
                except Exception as e:
                    print(f"[DB] Warning: Failed to seed resumes from CSV: {e}")

        # Check existing interviews count
        cursor.execute("SELECT COUNT(*) FROM interviews")
        interview_count = cursor.fetchone()[0]

        if interview_count == 0:
            sample_interviews = [
                (
                    "Alex Johnson",
                    "alex.johnson@example.com",
                    "Senior Machine Learning Engineer",
                    "Nuna",
                    "Dr. Emily Chen (Lead AI Scientist)",
                    "Today, 3:30 PM (IST)",
                    "meet-ai-ml92",
                    "https://meet.google.com/new",
                    "Ready to Join",
                    "Round 2: System Architecture & Deep Learning Coding."
                ),
                (
                    "Candidate #16",
                    "candidate16@example.com",
                    "Database Administrator (DBA)",
                    "Wish",
                    "Marcus Vance (Head of Infrastructure)",
                    "Tomorrow, 11:00 AM (IST)",
                    "meet-dba-404",
                    "https://meet.google.com/new",
                    "Scheduled",
                    "Round 1: SQL Optimization, Sharding & Scaling Discussion."
                )
            ]
            for itw in sample_interviews:
                if self.db_type == "mysql":
                    cursor.execute("""
                        INSERT INTO interviews 
                        (candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, itw)
                else:
                    cursor.execute("""
                        INSERT INTO interviews 
                        (candidate_name, candidate_email, job_title, company, interviewer_name, scheduled_time, meet_code, meet_url, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, itw)
            conn.commit()
            print("[DB] Seeded initial interview demo sessions.")

        cursor.close()
        conn.close()

db_manager = DatabaseManager()
