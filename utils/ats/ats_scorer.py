import re
import logging
import fitz  # PyMuPDF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer, util
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ATSScorer:
    def __init__(self, job_description, resume_path=None, resume_text=None):
        self.job_description = job_description
        self.model = SentenceTransformer('bert-base-nli-mean-tokens')
        
        if resume_path:
            self.resume = self.extract_text_from_pdf(resume_path)
        elif resume_text:
            self.resume = resume_text
        else:
            raise ValueError("Either resume_path or resume_text must be provided.")
        
        logging.info("Initialized ATSScorer with resume text extracted from PDF.")
        
        # Extract data from the job description text
        self.parsed_job_data = self.parse_job_description(self.job_description)

    def extract_text_from_pdf(self, pdf_path):
        logging.info(f"Extracting text from PDF: {pdf_path}")
        doc = fitz.open(pdf_path)
        text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        return text.strip()

    def parse_job_description(self, job_description_text):
        # Extract required skills and preferred skills
        skills_pattern = r"(?i)(?:requirements|qualifications|responsibilities|required skills):\s*([\s\S]*?)(?:nice to have|preferred qualifications|preferred skills|why join us|about us|benefits|$)"
        skills_match = re.search(skills_pattern, job_description_text)

        required_skills = []
        preferred_skills = []

        if skills_match:
            skills_text = skills_match.group(1)
            # Split the skills by common separators such as newlines, bullet points, commas, etc.
            skills_list = re.split(r'\n|•|-|,|\band\b', skills_text)
            skills_list = [skill.strip().lower() for skill in skills_list if skill.strip()]
            # Consider first half of the list as required and the second as preferred (if explicitly mentioned)
            required_skills = skills_list[:]
    
        # Enhanced pattern to extract years of experience
        experience_pattern = r"(?i)(\d+)\s*(?:\+?\s*years?|yrs)\s+(?:of\s+)?(?:experience|exp)"
        experience_match = re.search(experience_pattern, job_description_text)
        required_experience_years = int(experience_match.group(1)) if experience_match else 0
        
        # Enhanced pattern to extract education requirements
        education_pattern = r"(?i)(bachelor|master|ph\.?d)\s+of\s+(science|arts|engineering|computer\s?science)"
        education_match = re.findall(education_pattern, job_description_text)
        required_education = [" ".join(match).strip() for match in education_match]
        
        parsed_data = {
            'skills': {
                'required': required_skills,
                'preferred': preferred_skills
            },
            'experience_years': required_experience_years,
            'education': required_education
        }
        
        logging.info(f"Parsed Job Data: {parsed_data}")
        return parsed_data

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

    def compute_tfidf_similarity(self):
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([self.resume, self.job_description])
        similarity_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        logging.info(f"Textual similarity (TF-IDF Cosine Similarity) => Score: {similarity_score[0][0]:.2f}")
        return similarity_score[0][0]

    def compute_bert_similarity(self):
        resume_embedding = self.model.encode(self.resume, convert_to_tensor=True)
        job_description_embedding = self.model.encode(self.job_description, convert_to_tensor=True)
        similarity_score = util.pytorch_cos_sim(resume_embedding, job_description_embedding)
        logging.info(f"Semantic similarity (BERT Cosine Similarity) => Score: {similarity_score.item():.2f}")
        return similarity_score.item()

    def compute_keyword_relevance(self):
        # Example: count the number of times key terms appear in both resume and job description
        resume_keywords = set(self.resume.lower().split())
        job_description_keywords = set(self.job_description.lower().split())
        common_keywords = resume_keywords.intersection(job_description_keywords)
        relevance_score = len(common_keywords) / len(job_description_keywords) if job_description_keywords else 0
        logging.info(f"Keyword relevance score: {relevance_score:.2f}")
        return relevance_score

    def compute_overall_score(self, resume_data):
        skill_score = self.match_skills(resume_data['skills'], self.parsed_job_data['skills'])
        experience_score = self.match_experience(resume_data['experience_years'], self.parsed_job_data['experience_years'])
        education_score = self.match_education(resume_data['education'], self.parsed_job_data['education'])
        tfidf_similarity_score = self.compute_tfidf_similarity()
        bert_similarity_score = self.compute_bert_similarity()
        keyword_relevance_score = self.compute_keyword_relevance()

        overall_score = 0.3 * skill_score + 0.25 * experience_score + \
                        0.15 * education_score + 0.1 * keyword_relevance_score + \
                        0.1 * bert_similarity_score + 0.1 * tfidf_similarity_score
                        
        logging.info(f"Final computed overall score => {overall_score:.2f}")
        return overall_score

    def score(self, resume_data):
        logging.info("Starting the scoring process...")
        return self.compute_overall_score(resume_data)

# Example usage:
resume_pdf_path = 'data/resume.pdf'

resume_data = {
    'skills': ['Python', 'Machine Learning', 'Data Analysis'],
    'experience_years': 5,
    'education': 'Bachelor of Science in Computer Science',
    # 'text' key is not needed because we're loading the resume from a PDF
}

job_description_text = """
At Weights & Biases, our mission is to build the best tools for AI developers. We founded our company on the insight that while there were excellent tools for developers to build better code, there were no similarly great tools to help ML practitioners build better models. Starting with our first experiment tracking product, we have since expanded our solution into a comprehensive AI developer platform for organizations focused on building their own deep learning models and generative AI applications.

Weights & Biases is a Series C company with $250M in funding and over 200 employees. We proudly serve over 1,000 customers and more than 30 foundation model builders including customers such as OpenAI, NVIDIA, Microsoft, and Toyota.

As the software engineer in charge of Weights & Biases Sweeps product, you’ll build and maintain key features to allow users to effectively tune hyperparameters. You’ll work on the next generation of sweeps, with a focus on allowing users to effectively distribute their hyperparameter tuning scripts across clusters and cloud infrastructure. You’ll also contribute to the development of Weights & Biases Launch, an execution layer being actively developed on the Weights & Biases platform. You will have the opportunity to design system architecture and APIs so users can easily send their workflows to the cloud, or local clusters.
Responsibilities
Design and implement features to help users build and tune the best models by leveraging large scale compute.
Lead the maintenance of our existing Sweeps product and ensure a seamless transition to the next generation.
Contribute to the design and implementation to an execution platform built on Weights & Biases.
Focus on our end users and listen to customer feedback in order to deliver value.
Requirements
4+ years of experience in software engineering
Strong software engineering fundamentals and knowledge of at least 1 modern programming language (Python, Go, Typescript, GraphQL, etc)
Strong empathy for ML practitioners with a keen interest in understanding and addressing their challenges.
A desire to be self-driven and find the path to greatest impact.
Nice to have: experience working with ML Engineers and building tools to allow them to easily connect with their compute.
"""

scorer = ATSScorer(job_description_text, resume_path=resume_pdf_path)
score = scorer.score(resume_data)
print(f"Final score: {score:.2f}")

