import random
import string
import requests
from config import Config

def generate_otp(length=6):
    """Generate a random numeric OTP of specified length."""
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(to_email, otp, purpose="Registration"):
    """Send an OTP email to the given address."""
    if Config.MOCK_EMAIL:
        print("\n" + "="*50)
        print(f" MOCK EMAIL: Sent OTP [{otp}] for {purpose} to {to_email} ")
        print("="*50 + "\n")
        return True
        
    if not Config.BREVO_API_KEY:
        print("Warning: BREVO_API_KEY not configured. OTP not sent.")
        return False

    print("Brevo sender:", Config.BREVO_FROM_EMAIL)
        
    subject = f"Your Avora {purpose} OTP"
    body = f"""
    <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #0f2d4a;">Avora &middot; KMCLU University Platform</h2>
                <p>Hello,</p>
                <p>You have requested a One-Time Password (OTP) for <strong>{purpose}</strong> on the Avora University Platform:</p>
                <div style="background-color: #f1f5f9; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0; border: 2px solid #cbd5e1;">
                    <h1 style="margin: 0; letter-spacing: 6px; color: #0f2d4a; font-family: monospace;">{otp}</h1>
                </div>
                <p>This verification code is valid for {Config.OTP_EXPIRY_SECONDS} seconds.</p>
                <p>If you did not initiate this request, please ignore this email or notify campus administration.</p>
                <br>
                <p>Office of Digital Governance,<br>Khwaja Moinuddin Chishti Language University</p>
            </div>
        </body>
    </html>
    """

    headers = {
        "api-key": Config.BREVO_API_KEY,
        "content-type": "application/json",
        "accept": "application/json"
    }

    payload = {
        "sender": {
            "name": Config.BREVO_FROM_NAME,
            "email": Config.BREVO_FROM_EMAIL
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": subject,
        "htmlContent": body
    }

    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers,
            timeout=10
        )
        if response.status_code in [200, 201, 202]:
            return True
        else:
            print(f"Brevo API error (status {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"Error sending email via Brevo API: {e}")
        return False
