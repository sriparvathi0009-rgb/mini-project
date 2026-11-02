import re

# Comprehensive tech and professional skills dictionary
SKILLS_TAXONOMY = {
    # Programming Languages
    "python", "java", "c++", "c#", "javascript", "typescript", "go", "rust",
    "ruby", "php", "swift", "kotlin", "r", "sql", "bash", "scala", "html", "css", "c",
    
    # AI / Machine Learning / Data Science
    "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "tensorflow", "pytorch", "keras", "scikit-learn",
    "pandas", "numpy", "matplotlib", "seaborn", "opencv", "nltk", "spacy",
    "transformers", "huggingface", "bert", "sbert", "llm", "generative ai",
    "data science", "data analysis", "data mining", "time series", "tableau", "power bi",
    
    # Big Data & Data Engineering
    "big data", "hadoop", "spark", "pyspark", "hive", "kafka", "mapreduce",
    "airflow", "etl", "data warehouse", "snowflake", "databricks",
    
    # Web & Backend Frameworks
    "flask", "django", "fastapi", "react", "angular", "vue", "node.js", "nodejs",
    "express", "next.js", "spring boot", "asp.net", "laravel", "graphql", "rest api", "tailwind",
    
    # Databases
    "mysql", "postgresql", "mongodb", "redis", "sqlite", "oracle", "cassandra",
    "elasticsearch", "dynamodb", "mariadb",
    
    # Cloud, DevOps & Tools
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "jenkins",
    "ci/cd", "git", "github", "gitlab", "terraform", "ansible", "linux", "unix",
    
    # Methodologies & Soft Skills
    "agile", "scrum", "microservices", "system design", "unit testing",
    "project management", "problem solving", "leadership", "communication"
}

def extract_email(text):
    if not text:
        return ""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else ""

def extract_phone(text):
    if not text:
        return ""
    # Matches formats like +1 234 567 8901, (123) 456-7890, 123-456-7890, +91 9876543210
    match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    return match.group(0).strip() if match else ""

def extract_name(text):
    if not text:
        return "Unknown Candidate"
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    for line in lines[:5]:
        line_lower = line.lower()
        if line_lower.startswith("name:"):
            return line.split(":", 1)[1].strip()
        if line_lower.startswith("name -"):
            return line.split("-", 1)[1].strip()
        if line_lower.startswith("candidate:"):
            return line.split(":", 1)[1].strip()
        # If line has 2-4 words, starts with capital, and doesn't look like a title or email
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
            if "@" not in line and "curriculum" not in line_lower and "resume" not in line_lower:
                return line
    return lines[0][:40] if lines else "Candidate"

def extract_skills_from_text(text):
    if not text:
        return []
    text_clean = " " + text.lower() + " "
    # Normalize punctuation
    text_clean = re.sub(r'[,;/|\(\)\[\]]', ' ', text_clean)
    found_skills = set()

    for skill in SKILLS_TAXONOMY:
        # Multi-word skills
        if " " in skill:
            pattern = r'(?:\b|\s)' + re.escape(skill) + r'(?:\b|\s)'
        else:
            # Single-word skill with exact word boundaries
            # Handle special symbols like c++, c#
            if skill in ["c++", "c#", ".net"]:
                pattern = re.escape(skill) + r'(?:\b|\s)'
            else:
                pattern = r'\b' + re.escape(skill) + r'\b'
        
        if re.search(pattern, text_clean):
            # Title case skill for clean presentation
            found_skills.add(skill.title() if len(skill) > 3 and not skill.isupper() else skill.upper())

    return sorted(list(found_skills))

def extract_education(text):
    if not text:
        return []
    degrees = []
    degree_patterns = [
        r'\b(?:b\.?tech|b\.?e\.?|b\.?s\.?|bachelor(?:s|\'s)?)\b(?:\s+in\s+[\w\s]+)?',
        r'\b(?:m\.?tech|m\.?s\.?|m\.?e\.?|master(?:s|\'s)?|mba)\b(?:\s+in\s+[\w\s]+)?',
        r'\b(?:ph\.?d\.?|doctorate)\b(?:\s+in\s+[\w\s]+)?',
        r'\b(?:diploma|associate degree)\b'
    ]
    for pattern in degree_patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for m in matches:
            d = m.strip().title()
            if d not in degrees:
                degrees.append(d)
    return degrees

def extract_experience_years(text):
    if not text:
        return 0
    matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)?', text, flags=re.IGNORECASE)
    if matches:
        try:
            return max(int(m) for m in matches if int(m) <= 40)
        except ValueError:
            pass
    return 0

def analyze_resume_full(resume_text, job_text=None):
    email = extract_email(resume_text)
    phone = extract_phone(resume_text)
    name = extract_name(resume_text)
    resume_skills = extract_skills_from_text(resume_text)
    education = extract_education(resume_text)
    exp_years = extract_experience_years(resume_text)

    result = {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": resume_skills,
        "education": education,
        "experience_years": exp_years,
        "matched_skills": [],
        "missing_skills": [],
        "skill_match_percentage": 0
    }

    if job_text:
        job_skills = extract_skills_from_text(job_text)
        resume_skill_set = set(s.lower() for s in resume_skills)
        job_skill_set = set(s.lower() for s in job_skills)

        matched = [s for s in job_skills if s.lower() in resume_skill_set]
        missing = [s for s in job_skills if s.lower() not in resume_skill_set]

        result["matched_skills"] = matched
        result["missing_skills"] = missing
        if job_skills:
            result["skill_match_percentage"] = round((len(matched) / len(job_skills)) * 100, 1)
        else:
            result["skill_match_percentage"] = 50.0

    return result
