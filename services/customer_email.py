from services.email_utils import email_sender
import os
from dotenv import load_dotenv

load_dotenv()

def send_customer_email(customer_data, customer_email):
    """Send email to customer with their information"""
    subject = "Thank you for your inquiry with Wise Choice Realty"
    
    # Create styled HTML email body
    body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f9f9f9;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 30px auto;
                background: #ffffff;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            h2 {{
                color: #2C3E50;
                margin-bottom: 10px;
            }}
            p {{
                color: #555;
                line-height: 1.6;
            }}
            ul {{
                background: #f1f5f9;
                padding: 15px;
                border-radius: 8px;
            }}
            li {{
                margin: 8px 0;
            }}
            .footer {{
                margin-top: 25px;
                font-size: 13px;
                color: #888;
                text-align: center;
            }}
            .brand {{
                font-weight: bold;
                color: #1E88E5;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Thank You for Reaching Out!</h2>
            <p>We appreciate your interest in <span class="brand">Wise Choice Realty</span>. 
            Our expert will contact you soon to discuss your needs and provide personalized assistance.</p>
            
            <h3>Your Details:</h3>
            <ul>
                <li><strong>Name:</strong> {customer_data.get('name', 'Not provided')}</li>
                <li><strong>Email:</strong> {customer_data.get('email', 'Not provided')}</li>
                <li><strong>Available Time:</strong> {customer_data.get('available_time', 'Not provided')}</li>
                <li><strong>Zip Code:</strong> {customer_data.get('zip_code', 'Not provided')}</li>
            </ul>
            
            <p>If you have any urgent questions, feel free to reply to this email and our team will get back to you promptly.</p>
            
            <p>Warm regards,<br>
            <strong>Wise Choice Realty Team</strong></p>
            
            <div class="footer">
                © {2025} Wise Choice Realty. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send email to customer and CC yourself
    email_sender.send_email(
        to_email=customer_email,
        subject=subject,
        body=body,
        cc_email=os.getenv("MY_EMAIL")  # CC yourself
    )
