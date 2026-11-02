from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')
emb1 = model.encode("I love machine learning", convert_to_tensor=True)
emb2 = model.encode("Artificial intelligence is fascinating", convert_to_tensor=True)

print("Similarity score:", util.cos_sim(emb1, emb2).item())