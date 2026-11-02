
import nltk
nltk.download('punkt_tab')
import pandas as pd
import string
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# Download NLTK resources (run once)
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

# Load datasets
jobs = pd.read_csv("glassdoor_jobs.csv")
resumes = pd.read_csv("resume_data.csv")

# Define preprocessing function
stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def preprocess(text):
    if pd.isnull(text):
        return ""
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    tokens = nltk.word_tokenize(text)
    tokens = [lemmatizer.lemmatize(t) for t in tokens if t not in stop_words]
    return " ".join(tokens)

# Clean job descriptions
jobs['clean_desc'] = jobs['Job Description'].apply(preprocess)

# Combine resume fields into one text column
resumes['resume_text'] = resumes[['career_objective','skills','responsibilities']].fillna('').agg(' '.join, axis=1)

# Clean resumes
resumes['clean_resume'] = resumes['resume_text'].apply(preprocess)

# Check results
print(jobs[['Job Title','clean_desc']].head())
print(resumes[['resume_text','clean_resume']].head())
# --- Preprocessing code here ---
jobs['clean_desc'] = jobs['Job Description'].apply(preprocess)
resumes['resume_text'] = resumes[['career_objective','skills','responsibilities']].fillna('').agg(' '.join, axis=1)
resumes['clean_resume'] = resumes['resume_text'].apply(preprocess)

# --- TF-IDF Vectorization ---
from sklearn.feature_extraction.text import TfidfVectorizer

corpus = jobs['clean_desc'].tolist() + resumes['clean_resume'].tolist()
vectorizer = TfidfVectorizer(max_features=5000)
tfidf_matrix = vectorizer.fit_transform(corpus)

job_vecs = tfidf_matrix[:len(jobs)]
resume_vecs = tfidf_matrix[len(jobs):]

print("Job vectors shape:", job_vecs.shape)
print("Resume vectors shape:", resume_vecs.shape)
from sklearn.metrics.pairwise import cosine_similarity

# Compute similarity matrix between jobs and resumes
similarity_matrix = cosine_similarity(job_vecs, resume_vecs)

print("Similarity matrix shape:", similarity_matrix.shape)

# Example: similarity score between first job and first resume
print("Job 1 vs Resume 1 similarity:", similarity_matrix[0][0])
import numpy as np

# For each job, find the resume with the highest similarity
best_matches = np.argmax(similarity_matrix, axis=1)
best_scores = np.max(similarity_matrix, axis=1)

# Show top 5 matches
for i in range(5):
    print(f"Job: {jobs['Job Title'].iloc[i]}")
    print(f"Best Resume Index: {best_matches[i]}")
    print(f"Similarity Score: {best_scores[i]:.4f}")
    print(f"Resume Text: {resumes['resume_text'].iloc[best_matches[i]][:200]}...\n")
import matplotlib.pyplot as plt

# Plot similarity scores for first 10 jobs
plt.figure(figsize=(10,6))
plt.bar(range(10), best_scores[:10])
plt.xticks(range(10), jobs['Job Title'].iloc[:10], rotation=45, ha='right')
plt.ylabel("Similarity Score")
plt.title("Top Resume Match Scores for First 10 Jobs")
plt.show()
# Create a DataFrame of matches
matches_df = pd.DataFrame({
    "Job Title": jobs['Job Title'],
    "Best Resume Index": best_matches,
    "Similarity Score": best_scores,
    "Matched Resume Text": [resumes['resume_text'].iloc[idx] for idx in best_matches]
})

# Save to CSV
matches_df.to_csv("job_resume_matches.csv", index=False)

print("Job–Resume matches saved to job_resume_matches.csv")
import matplotlib.pyplot as plt

plt.figure(figsize=(10,6))
plt.bar(range(10), best_scores[:10])
plt.xticks(range(10), jobs['Job Title'].iloc[:10], rotation=45, ha='right')
plt.ylabel("Similarity Score")
plt.title("Top Resume Match Scores for First 10 Jobs")
plt.show()
import seaborn as sns
import matplotlib.pyplot as plt

# Plot a heatmap for the first 10 jobs vs first 10 resumes
plt.figure(figsize=(10,8))
sns.heatmap(similarity_matrix[:10,:10], annot=True, cmap="YlGnBu", fmt=".2f")
plt.xlabel("Resumes (first 10)")
plt.ylabel("Jobs (first 10)")
plt.title("Similarity Heatmap: Jobs vs Resumes")
plt.show()