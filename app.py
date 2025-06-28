from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from twilio.rest import Client
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import os

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Twilio credentials from .env
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")

# Twilio client
client = Client(TWILIO_SID, TWILIO_AUTH)

# In-memory session store (consider replacing with Redis/DB)
user_sessions = {}

# Sample doctor and slot data
doctors = {
    "1": "Dr. A (General Physician)",
    "2": "Dr. B (Dermatologist)",
    "3": "Dr. C (Cardiologist)"
}

slots = {
    "1": "10:00 AM",
    "2": "11:30 AM",
    "3": "4:00 PM"
}


# API: Send message manually via POST
class MessageRequest(BaseModel):
    to: str
    message: str

@app.post("/send-message")
def send_message(req: MessageRequest):
    try:
        to_number = f"whatsapp:{req.to}"
        sent = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to_number,
            body=req.message
        )
        return {"success": True, "sid": sent.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API: Receive WhatsApp message via webhook
@app.post("/whatsapp-webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    user_msg = Body.strip().lower()
    phone = From
    state = user_sessions.get(phone, {"step": "start"})

    if user_msg in ["book appointment", "appointment", "book"]:
        user_sessions[phone] = {"step": "choose_doctor"}
        return send_whatsapp(phone, """Great! Please choose a doctor:
1. Dr. A (General Physician)
2. Dr. B (Dermatologist)
3. Dr. C (Cardiologist)

Reply with 1, 2, or 3.""")

    elif state["step"] == "choose_doctor" and user_msg in doctors:
        selected_doctor = doctors[user_msg]
        user_sessions[phone] = {"step": "choose_time", "doctor": selected_doctor}
        return send_whatsapp(phone, f"""You've selected {selected_doctor}.
Available slots:
1. 10:00 AM
2. 11:30 AM
3. 4:00 PM

Reply with the slot number to continue.""")

    elif state["step"] == "choose_time" and user_msg in slots:
        selected_slot = slots[user_msg]
        selected_doctor = state["doctor"]
        user_sessions[phone] = {
            "step": "awaiting_confirmation",
            "doctor": selected_doctor,
            "time": selected_slot
        }
        return send_whatsapp(phone, f"""You chose:
Doctor: {selected_doctor}
Time: {selected_slot}

Reply 'Confirm' to finalize or 'Cancel' to abort.""")

    elif state["step"] == "awaiting_confirmation" and user_msg == "confirm":
        doctor = state["doctor"]
        time = state["time"]
        user_sessions[phone] = {"step": "done"}
        return send_whatsapp(phone, f"""✅ Appointment confirmed with {doctor} at {time}.
Thank you! Reply 'Book' to schedule another.""")

    elif user_msg == "cancel":
        user_sessions[phone] = {"step": "start"}
        return send_whatsapp(phone, "❌ Your appointment process has been cancelled. Type 'Book' to start again.")

    else:
        return send_whatsapp(phone, "I didn't understand that. Please type 'Book' to start booking an appointment.")


# Helper function to send WhatsApp message
def send_whatsapp(to_number, body):
    client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=to_number,
        body=body
    )
    return "OK"
