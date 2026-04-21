"""Messaging blasts via SendGrid (email) and Twilio (SMS)."""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Header, Cookie

from config import db
from auth import verify_session
from models import MessageBlastRequest

router = APIRouter(prefix="/messages")


@router.post("/send")
async def send_message_blast(data: MessageBlastRequest, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)

    recipients_emails = []
    recipients_phones = []

    if data.recipient_group in ["all", "newsletter"]:
        subs = await db.newsletter_subscribers.find({}, {"_id": 0, "email": 1}).to_list(1000)
        recipients_emails.extend([s["email"] for s in subs])

    if data.recipient_group in ["all", "giveaway"]:
        entries = await db.giveaway_entries.find({}, {"_id": 0, "email": 1, "phone": 1}).to_list(1000)
        recipients_emails.extend([e["email"] for e in entries if e.get("email")])
        recipients_phones.extend([e["phone"] for e in entries if e.get("phone")])

    if data.recipient_group in ["all", "loyalty"]:
        members = await db.loyalty_members.find({}, {"_id": 0, "phone": 1}).to_list(1000)
        recipients_phones.extend([m["phone"] for m in members if m.get("phone")])

    recipients_emails = list(set(recipients_emails))
    recipients_phones = list(set([p for p in recipients_phones if p]))

    email_sent = 0
    sms_sent = 0
    errors = []

    if data.channel in ["email", "both"] and recipients_emails:
        sendgrid_key = os.environ.get("SENDGRID_API_KEY")
        sender_email = os.environ.get("SENDER_EMAIL")
        if sendgrid_key and sender_email:
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                sg = SendGridAPIClient(sendgrid_key)
                for email_addr in recipients_emails:
                    try:
                        message = Mail(from_email=sender_email, to_emails=email_addr, subject=data.subject, html_content=data.body)
                        sg.send(message)
                        email_sent += 1
                    except Exception as e:
                        errors.append(f"Email to {email_addr}: {str(e)}")
            except Exception as e:
                errors.append(f"SendGrid init error: {str(e)}")
        else:
            errors.append("SendGrid not configured (missing SENDGRID_API_KEY or SENDER_EMAIL)")

    if data.channel in ["sms", "both"] and recipients_phones:
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER")
        if twilio_sid and twilio_token and twilio_phone:
            try:
                from twilio.rest import Client as TwilioClient
                twilio_client = TwilioClient(twilio_sid, twilio_token)
                for phone in recipients_phones:
                    try:
                        twilio_client.messages.create(body=data.body, from_=twilio_phone, to=phone)
                        sms_sent += 1
                    except Exception as e:
                        errors.append(f"SMS to {phone}: {str(e)}")
            except Exception as e:
                errors.append(f"Twilio init error: {str(e)}")
        else:
            errors.append("Twilio not configured (missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_PHONE_NUMBER)")

    blast_record = {
        "id": str(uuid.uuid4()),
        "subject": data.subject,
        "body": data.body,
        "channel": data.channel,
        "recipient_group": data.recipient_group,
        "email_count": email_sent,
        "sms_count": sms_sent,
        "total_emails": len(recipients_emails),
        "total_phones": len(recipients_phones),
        "errors": errors,
        "sent_at": datetime.now(timezone.utc).isoformat()
    }
    await db.message_blasts.insert_one(blast_record)

    return {
        "email_sent": email_sent,
        "sms_sent": sms_sent,
        "total_emails": len(recipients_emails),
        "total_phones": len(recipients_phones),
        "errors": errors,
        "message": f"Sent {email_sent} emails and {sms_sent} SMS messages"
    }


@router.get("/history")
async def get_message_history(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    blasts = await db.message_blasts.find({}, {"_id": 0}).sort("sent_at", -1).to_list(50)
    return {"blasts": blasts, "total": len(blasts)}
