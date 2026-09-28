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
def get_admin_recipients():
    r = requests.get(f"{api_base}/scraper/recipients", headers={"x-api-key": scraper_api_key}, timeout=15)
    r.raise_for_status()

    print("status:", r.status_code)

    recipients = r.json()

    # Only admin emails
    return [
        recipient["email"]
        for recipient in recipients
        if recipient["recipient_type"] == "admin"
    ]

# Send email
def send_email(subject: str, body: str, recipients: list[str]):
    if not recipients:
        print("[ALERT ERROR]: No admin recipients configured")
        return 1

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from_email
    msg["To"] = ", ".join(recipients)
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
subject = sys.argv[1]
body = sys.argv[2]

recipients = get_admin_recipients()

# Send Email
send_email(subject=subject, body=body, recipients=recipients)