from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer, util
import numpy as np

class ATSScorer:
    def __init__(self, job_description, resume):
        self.job_description = job_description
        self.resume = resume
        self.model = SentenceTransformer('bert-base-nli-mean-tokens')

    def match_skills(self, resume_skills, job_skills):
        required_skills = job_skills.get('required', [])
        preferred_skills = job_skills.get('preferred', [])
        
        required_match_count = sum([1 for skill in required_skills if skill in resume_skills])
        preferred_match_count = sum([1 for skill in preferred_skills if skill in resume_skills])
        
        skill_score = (required_match_count * 2) + preferred_match_count
        return skill_score / (len(required_skills) * 2 + len(preferred_skills))

    def match_experience(self, resume_experience_years, job_experience_years):
        experience_score = min(resume_experience_years / job_experience_years, 1)
        return experience_score

    def match_education(self, resume_education, job_education):
        return 1 if resume_education in job_education else 0

    def compute_text_similarity(self):
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([self.resume, self.job_description])
        similarity_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return similarity_score[0][0]

    def compute_embedding_similarity(self):
        resume_embedding = self.model.encode(self.resume, convert_to_tensor=True)
        job_description_embedding = self.model.encode(self.job_description, convert_to_tensor=True)
        similarity_score = util.pytorch_cos_sim(resume_embedding, job_description_embedding)
        return similarity_score.item()

    def compute_overall_score(self, resume_data, job_data):
        skill_score = self.match_skills(resume_data['skills'], job_data['skills'])
        experience_score = self.match_experience(resume_data['experience_years'], job_data['experience_years'])
        education_score = self.match_education(resume_data['education'], job_data['education'])
        text_similarity_score = self.compute_text_similarity()
        embedding_similarity_score = self.compute_embedding_similarity()

        # Customize your weighting strategy here
        final_score = (0.3 * skill_score +
                       0.3 * experience_score +
                       0.2 * education_score +
                       0.1 * text_similarity_score +
                       0.1 * embedding_similarity_score)
        return final_score

    def score(self, resume_data, job_data):
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
