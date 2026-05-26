import os
import logging

logger = logging.getLogger(__name__)

TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "")


def send_sms_alert(phone_number: str, message: str, google_drive_link: str = None) -> bool:
    """Send an SMS alert for emergency reporting.

    This function is a stand-in for future SMS integration.
    It currently supports Twilio if credentials are configured.
    """
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_PHONE:
        logger.warning("SMS service not configured: TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE required")
        return False

    body = message
    if google_drive_link:
        body = f"{body}\nWatch the incident: {google_drive_link}"

    try:
        from twilio.rest import Client

        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            body=body,
            from_=TWILIO_PHONE,
            to=phone_number
        )
        logger.info(f"✓ SMS alert sent to {phone_number}")
        return True
    except ImportError:
        logger.warning("Twilio library is not installed; SMS send skipped")
        return False
    except Exception as exc:
        logger.error(f"SMS send failed: {exc}")
        return False
