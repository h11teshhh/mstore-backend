import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
from datetime import datetime, timedelta
import os

def send_otp_email(to_email: str, otp: str):
    sender_email = os.getenv('EMAIL_USER', 'nilkanthtraders82@gmail.com')
    password = os.getenv('EMAIL_PASS')
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = 'MStore Password Reset OTP'
    body = f'''<html><body><h2>MStore</h2><p>Your OTP is {otp}. Valid for 10 minutes.</p><p>Do not share this code.</p></body></html>'''
    msg.attach(MIMEText(body, 'html'))
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)

def generate_otp():
    return ''.join([str(random.randint(0,9)) for _ in range(6)])