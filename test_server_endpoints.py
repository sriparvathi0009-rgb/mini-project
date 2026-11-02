import json
from app import app

def run_tests():
    client = app.test_client()

    print("--- 1. Testing GET / ---")
    res = client.get('/')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print("GET / passed! HTML returned length:", len(res.data))

    print("\n--- 2. Testing GET /api/stats ---")
    res = client.get('/api/stats')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    stats = res.get_json()
    print("Stats:", stats)
    assert stats["total_jobs"] > 0, "Jobs should be seeded!"
    assert stats["total_resumes"] > 0, "Resumes should be seeded!"

    print("\n--- 3. Testing GET /api/jobs ---")
    res = client.get('/api/jobs')
    assert res.status_code == 200
    jobs_data = res.get_json()
    print(f"Retrieved {len(jobs_data['jobs'])} jobs.")
    print("Sample job:", jobs_data['jobs'][0]['title'])

    print("\n--- 4. Testing POST /api/match_resume ---")
    sample_resume = """
    Alex Johnson
    alex.johnson@example.com | (555) 234-5678
    San Francisco, CA
    
    Professional Summary:
    Experienced Machine Learning Engineer and Data Scientist with 4+ years of expertise building end-to-end NLP pipelines, deep learning models, and scalable REST APIs.
    
    Education:
    B.Tech in Computer Science, University of California
    
    Technical Skills:
    Python, PyTorch, TensorFlow, Scikit-Learn, Docker, SQL, Pandas, NumPy, NLP, Transformers, AWS, Git
    
    Experience:
    Senior AI Engineer at Tech Corp (2021-Present)
    - Developed transformer-based text categorization models improving accuracy by 25%.
    - Deployed models using Docker and Flask APIs on AWS ECS.
    """
    res = client.post('/api/match_resume', data={'resume_text': sample_resume})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    result = res.get_json()
    print("Candidate parsed:", result["candidate"]["name"], "| Email:", result["candidate"]["email"])
    print("Extracted Skills:", result["candidate"]["skills"])
    print("Number of Top Matches returned:", len(result["top_matches"]))
    for m in result["top_matches"][:3]:
        print(f"  -> Job: {m['job_title']} ({m['company']}) | Score: {m['score']}% | Matched: {m['matched_skills']}")

    print("\n--- 5. Testing GET /matches ---")
    res = client.get('/matches')
    assert res.status_code == 200
    print("GET /matches passed! Length:", len(res.data))

    print("\n--- 6. Testing GET /interview (Google Meet Lobby) ---")
    res = client.get('/interview')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert b"Google Meet Interview Lobby" in res.data, "Lobby title should be in page"
    assert b"Join Google Meet Call Now" in res.data, "Join button should be in page"
    print("GET /interview passed! Rendered bytes:", len(res.data))

    print("\n--- 7. Testing GET /interview with query params ---")
    res = client.get('/interview?candidate=Sarah+Connor&role=AI+Ethics+Lead&company=Cyberdyne')
    assert res.status_code == 200
    assert b"Sarah Connor" in res.data
    assert b"AI Ethics Lead" in res.data
    print("GET /interview with query params passed!")

    print("\n--- 8. Testing POST /api/interviews (Create Interview) ---")
    new_itw = {
        "candidate_name": "David Miller",
        "candidate_email": "david.m@example.com",
        "job_title": "Full Stack Python Architect",
        "company": "DeepMind Partner",
        "scheduled_time": "Friday, 2:00 PM",
        "interviewer_name": "Engineering Lead"
    }
    res = client.post('/api/interviews', json=new_itw)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    created = res.get_json()
    print("Created interview session:", created)
    assert created["success"] is True
    assert "meet_code" in created

    print("\n--- 9. Testing GET /interview/<id> ---")
    res = client.get(f"/interview/{created['interview_id']}")
    assert res.status_code == 200
    assert b"David Miller" in res.data
    print(f"GET /interview/{created['interview_id']} passed!")

    print("\n--- 10. Testing aliases /schedule_interview and /schedule ---")
    res1 = client.get('/schedule_interview?candidate=John+Doe&role=Backend+Developer')
    assert res1.status_code == 200
    assert b"John Doe" in res1.data
    res2 = client.get('/schedule')
    assert res2.status_code == 200
    print("/schedule_interview and /schedule aliases passed!")

    print("\n===============================")
    print("ALL FLASK TEST CLIENT CHECKS PASSED!")
    print("===============================")

if __name__ == "__main__":
    run_tests()
