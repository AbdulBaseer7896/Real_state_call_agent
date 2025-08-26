# sendgrid_utils.py
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_sendgrid_email(to_email, subject, body, cc_email=None):
    message = Mail(
        from_email=os.getenv("EMAIL_USERNAME"),
        to_emails=to_email,
        subject=subject,
        html_content=body
    )
    
    if cc_email:
        message.add_cc(cc_email)
    
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(f"Email sent with status code: {response.status_code}")
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False