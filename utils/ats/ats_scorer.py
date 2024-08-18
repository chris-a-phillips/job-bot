import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer, util
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ATSScorer:
    def __init__(self, job_description, resume):
        self.job_description = job_description
        self.resume = resume
        self.model = SentenceTransformer('bert-base-nli-mean-tokens')
        logging.info("Initialized ATSScorer")

    def match_skills(self, resume_skills, job_skills):
        required_skills = job_skills.get('required', [])
        preferred_skills = job_skills.get('preferred', [])
        
        required_match_count = sum([1 for skill in required_skills if skill in resume_skills])
        preferred_match_count = sum([1 for skill in preferred_skills if skill in resume_skills])
        
        skill_score = (required_match_count * 2) + preferred_match_count
        max_score = len(required_skills) * 2 + len(preferred_skills)
        logging.info(f"Matched {required_match_count}/{len(required_skills)} required skills and {preferred_match_count}/{len(preferred_skills)} preferred skills.")
        
        return skill_score / max_score if max_score > 0 else 0

    def match_experience(self, resume_experience_years, job_experience_years):
        experience_score = min(resume_experience_years / job_experience_years, 1)
        logging.info(f"Experience match: {resume_experience_years} years (Resume) / {job_experience_years} years (Job) => Score: {experience_score:.2f}")
        return experience_score

    def match_education(self, resume_education, job_education):
        education_match = 1 if resume_education in job_education else 0
        logging.info(f"Education match: {resume_education} (Resume) in {job_education} (Job) => Score: {education_match}")
        return education_match

    def compute_text_similarity(self):
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([self.resume, self.job_description])
        similarity_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        logging.info(f"Textual similarity (TF-IDF Cosine Similarity) => Score: {similarity_score[0][0]:.2f}")
        return similarity_score[0][0]

    def compute_embedding_similarity(self):
        resume_embedding = self.model.encode(self.resume, convert_to_tensor=True)
        job_description_embedding = self.model.encode(self.job_description, convert_to_tensor=True)
        similarity_score = util.pytorch_cos_sim(resume_embedding, job_description_embedding)
        logging.info(f"Semantic similarity (BERT Cosine Similarity) => Score: {similarity_score.item():.2f}")
        return similarity_score.item()

    def compute_overall_score(self, resume_data, job_data):
        skill_score = self.match_skills(resume_data['skills'], job_data['skills'])
        experience_score = self.match_experience(resume_data['experience_years'], job_data['experience_years'])
        education_score = self.match_education(resume_data['education'], job_data['education'])
        text_similarity_score = self.compute_text_similarity()
        embedding_similarity_score = self.compute_embedding_similarity()

        final_score = (0.3 * skill_score +
                       0.3 * experience_score +
                       0.2 * education_score +
                       0.1 * text_similarity_score +
                       0.1 * embedding_similarity_score)
        logging.info(f"Final computed score => {final_score:.2f}")
        return final_score

    def score(self, resume_data, job_data):
        logging.info("Starting the scoring process...")
        return self.compute_overall_score(resume_data, job_data)

# Example usage:
resume_data = {
    'skills': ['Python', 'Machine Learning', 'Data Analysis'],
    'experience_years': 5,
    'education': 'Bachelor of Science in Computer Science',
    'text': '...full resume text...'
}

job_data = {
    'skills': {
        'required': ['Python', 'Data Analysis'],
        'preferred': ['Machine Learning', 'NLP']
    },
    'experience_years': 3,
    'education': ['Bachelor of Science in Computer Science', 'Master of Science in Data Science'],
    'text': '...full job description text...'
}

job_description_text = job_data['text']
resume_text = resume_data['text']

scorer = ATSScorer(job_description_text, resume_text)
score = scorer.score(resume_data, job_data)
print(f"Final score: {score:.2f}")

