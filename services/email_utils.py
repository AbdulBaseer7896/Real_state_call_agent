# email_utils.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

class EmailSender:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.email_username = os.getenv("EMAIL_USERNAME")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.my_email = os.getenv("MY_EMAIL")
    
    def send_email(self, to_email, subject, body, cc_email=None):
        """Send email to customer and CC myself"""
        if not all([self.smtp_server, self.email_username, self.email_password]):
            print("Email configuration missing. Cannot send email.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add CC if specified
            if cc_email:
                msg['Cc'] = cc_email
            
            # Add body to email
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_username, self.email_password)
                
                # Determine recipients (to + cc)
                recipients = [to_email]
                if cc_email:
                    recipients.append(cc_email)
                
                server.sendmail(self.email_username, recipients, msg.as_string())
            
            print(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False

# # Create a global instance
email_sender = EmailSender()




# # Test email
# email_sender.send_email(
#     to_email="abdulbasirqazi@gmail.com",
#     subject="Test Email",
#     body="<h1>This is a test email</h1><p>If you received this, your email setup is working!</p>",
#     cc_email=os.getenv("MY_EMAIL")
# )

# import smtplib
# from email.mime.text import MIMEText

# myEmail = 'abdulbasirqazi@gmail.com'   # must be exact Gmail
# app_password = 'opkk zzoj psop guxm'   # 16-char App Password from Google

# smtp_server = 'smtp.gmail.com'
# smtp_port = 587

# msg = MIMEText("This is a testing email")
# msg['Subject'] = 'Nothing, just subject'
# msg['From'] = myEmail
# msg['To'] = 'abdulbasirqazi7896@gmail.com'
# # msg['Cc'] = 'friend@example.com' 
# server = smtplib.SMTP(smtp_server, smtp_port)
# server.ehlo()
# server.starttls()
# server.ehlo()

# server.login(myEmail, app_password)
# server.send_message(msg)
# server.quit()
