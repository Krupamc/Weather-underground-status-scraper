# Sends Email Alerts
import os, sys, smtplib, ssl, requests
from email.message import EmailMessage

# Get Config
api_base = os.getenv("API_BASE", "http://web:8000")
scraper_api_key = os.getenv("SCRAPER_API_KEY", "")
smtp_host = os.getenv("SERVER", "")
smtp_port = int(os.getenv("PORT", "587"))
smtp_username = os.getenv("USERNAME", "")
smtp_password = os.getenv("PASSWORD", "")
smtp_from_email = os.getenv("FROM_EMAIL", "")

# Get all admin/global emails
def get_recipients(email_type: str):
    if email_type == "admin":
        url=f"{api_base}/scraper/recipients"
    elif email_type == "weather":
        url=f"{api_base}/scraper/weather/recipients"

    r = requests.get(url, headers={"x-api-key": scraper_api_key}, timeout=15)
    r.raise_for_status()

    print("status:", r.status_code)

    recipients = r.json()

    
    # Only admin emails
    if email_type == "admin":
        return [
            recipient["email"]
            for recipient in recipients
            if recipient["recipient_type"] == "admin"
        ]

    elif email_type == "weather":
        return [
            recipient["email"]
            for recipient in recipients
            if recipient["recipient_type"] == ""
        ]

# Send email
def send_email(subject: str, body: str, recipients: list[str]):
    if not recipients:
        print("[ALERT ERROR]: No admin recipients configured")
        return 1

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from_email
    msg["Bcc"] = ", ".join(recipients)
    msg.set_content(body)

    context = ssl.create_default_context()

    # Send Email
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_username, smtp_password)
        server.send_message(msg)

    return 0

# Get Arguments from terminal:
if len(sys.argv) < 3:
    print("[ERROR]: Arguments Missing.")
    print('"SUBJECT" "BODY"')
    sys.exit(1)

# Set Variables
email_type = sys.argv[1]
subject = sys.argv[2]
body = sys.argv[3]

recipients = get_recipients(email_type)

# Send Email
send_email(subject=subject, body=body, recipients=recipients)