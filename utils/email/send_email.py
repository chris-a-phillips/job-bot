import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()  # Loads the .env file into your environment
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

def send_email(jobs_list):
    if len(jobs_list) == 0:
        print("No jobs found to send email for.")
        return
    from_email = SENDER_EMAIL
    password = SENDER_PASSWORD
    to_email = RECIPIENT_EMAIL
    subject = create_subject()
    html_body = create_body_text(jobs_list)

    # Set up the MIME
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    # Attach the body with the msg instance
    msg.attach(MIMEText(html_body, 'html'))


    # Create an SMTP session
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()  # Start TLS for security

    # Login to the server
    server.login(from_email, password)

    # Convert the message to a string and send it
    server.sendmail(from_email, to_email, msg.as_string())
    print("Email sent successfully!")

    # Close the connection
    server.quit()
    return


def create_subject():
    now = datetime.now()  # Get the current date and time
    timestamp = now.strftime("%a, %b %d, %Y %H:%M")
    return f"Job Bot Run - {timestamp}"


def create_body_text(jobs_list):
    body = "<html><body>"
    for i, job in enumerate(jobs_list, start=1):
        body += f"""
        <hr style="border: 1px solid #000;">
        <h2 style="margin: 0;">Job {i}: {job['title']}</h2>
        <h3 style="margin: 0;">Company: {job['company']}</h3>
        <hr style="border: 1px solid #000;">
        <h4 style="margin: 0;">Job Description:</h4>
        <p>{job['job_description']}</p>
        <h4 style="margin: 0;">Confidence Score:</h4>
        <p><strong>{job['confidence_score']}</strong></p>
        <h4 style="margin: 0;">Analysis:</h4>
        <p>{job['analysis']}</p>
        <h4 style="margin: 0;">Job URL:</h4>
        <p><a href="{job['job_url']}">{job['job_url']}</a></p>
        <hr style="border: 1px solid #000;">
        """
    body += "</body></html>"
    return body

# TODO: add body text to email for list of jobs
# TODO: add attachment to email for log file of run
