"""
📧 Email Service — v1.0
========================
File: app/core/email_service.py

Real SMTP email sending for the Finance Agent.
Reads credentials from .env. If no credentials, gracefully falls back to DB log-only.
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.server   = os.getenv("MAIL_SERVER")
        self.port     = int(os.getenv("MAIL_PORT", "587"))
        self.username = os.getenv("MAIL_USERNAME")
        self.password = os.getenv("MAIL_PASSWORD")
        self.sender   = os.getenv("MAIL_FROM", "noreply@erp.local")
        self.use_tls  = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
        
        self.is_configured = bool(self.server and self.username and self.password)
        if self.is_configured:
            logger.info("📧 EmailService configured via SMTP (%s:%s)", self.server, self.port)
        else:
            logger.warning("⚠️ EmailService NOT configured — running in simulated mode")

    async def send_email(self, to_email: str, subject: str, body: str) -> dict:
        """
        Send an email via SMTP.
        Returns: {"sent": bool, "simulated": bool, "method": str, "error": str}
        """
        if not to_email:
            return {"sent": False, "simulated": False, "method": "none", "error": "No recipient email provided"}

        if not self.is_configured:
            # Simulated mode
            logger.info("📧 [Simulated Email] To: %s | Subject: %s", to_email, subject)
            return {"sent": True, "simulated": True, "method": "log_only"}

        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = to_email

            context = ssl.create_default_context()
            
            if self.port == 465:
                # Implicit SSL
                with smtplib.SMTP_SSL(self.server, self.port, context=context) as smtp:
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            else:
                # Explicit TLS (STARTTLS)
                with smtplib.SMTP(self.server, self.port) as smtp:
                    if self.use_tls:
                        smtp.starttls(context=context)
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)
                    
            logger.info("📧 [SMTP] Email sent to: %s", to_email)
            return {"sent": True, "simulated": False, "method": "smtp"}
            
        except Exception as e:
            logger.error("❌ SMTP send failed: %s", e)
            return {"sent": False, "simulated": False, "method": "smtp", "error": str(e)}

# Singleton instance
email_service = EmailService()
