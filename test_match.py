from sentence_transformers import SentenceTransformer, util

# Load SBERT model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Example resume and job descriptions
resume_text = "Experienced Python developer with knowledge of Flask and MySQL."
job_desc1 = "Looking for a backend developer skilled in Python and Flask."
job_desc2 = "Hiring a data analyst with strong Excel and SQL skills."
job_desc3 = "Seeking a front-end developer with React and JavaScript expertise."

# Encode all texts
resume_emb = model.encode(resume_text, convert_to_tensor=True)
job_embs = model.encode([job_desc1, job_desc2, job_desc3], convert_to_tensor=True)

# Compute similarity scores
scores = util.cos_sim(resume_emb, job_embs)[0]

# Print results
print("Resume:", resume_text)
print("\nJob Matches:")
for i, job in enumerate([job_desc1, job_desc2, job_desc3]):
    print(f"{job} -> Score: {scores[i].item():.4f}")
