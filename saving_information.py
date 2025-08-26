#### This code is for implementation of direct prompt injection. No RAG.

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
import requests
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional
from prompt_real_statte_agent import SYSTEM_PROMPT
import hashlib
import json
import time

# Import the simplified Groq client
from services.Groq import GroqClient
from services.customer_email import send_customer_email
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env config
ULTRAVOX_API_KEY = os.getenv("ULTRAVOX_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
print("This is the key = " , ULTRAVOX_API_KEY)
ULTRAVOX_API_URL = "https://api.ultravox.ai/api/calls"
PORT = int(os.getenv("PORT", 4040))
BASE_URL = os.getenv("BASE_URL")

# Initialize Groq client
groq_client = GroqClient(api_key=GROQ_API_KEY)

retriever = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App startup – no embeddings or retrievers to load.")
    yield

app = FastAPI(lifespan=lifespan)

class DateRequest(BaseModel):
    date: Optional[str] = None

@app.post("/getDateTime")
async def get_date_info(request: Optional[DateRequest] = None):
    try:
        if request and request.date:
            date_obj = datetime.strptime(request.date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()

        return {
            "date": date_obj.strftime("%Y-%m-%d"),
            "time": date_obj.strftime("%H:%M:%S"),
            "day": date_obj.strftime("%A")
        }
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}   

def get_selected_tools():
    return [
        {
            "temporaryTool": {
                "modelToolName": "retrieve_and_answer",
                "description": "Retrieve answers for questions regarding jump passes.",
                "timeout": "15.0s",
                "dynamicParameters": [
                    {
                        "name": "query",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {"description": "User question", "type": "string"},
                        "required": True
                    }
                ],
                "http": {
                    "baseUrlPattern": f"{BASE_URL}/ragSearchjump",
                    "httpMethod": "POST"
                }
            }
        },
        {
            "temporaryTool": {
                "modelToolName": "get_date_info",
                "description": "Use to respond with the current date, time, or day of week for a specific date.",
                "timeout": "5.0s",
                "dynamicParameters": [
                    {
                        "name": "date",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {
                            "description": "Optional. A specific date (YYYY-MM-DD) to look up the weekday. If omitted, returns current date, time, and weekday.",
                            "type": "string"
                        },
                        "required": False
                    }
                ],
                "http": {
                    "baseUrlPattern": f"{BASE_URL}/getDateTime",
                    "httpMethod": "POST"
                }
            }
        },
        {
            "temporaryTool": {
                "modelToolName": "retrieve_and_answer_bday",
                "description": "Retrieve answers for questions regarding birthday party packages.",
                "timeout": "39.0s",
                "dynamicParameters": [
                    {
                        "name": "query",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {"description": "User question", "type": "string"},
                        "required": True
                    }
                ],
                "http": {
                    "baseUrlPattern": f"{BASE_URL}/ragSearchbday",
                    "httpMethod": "POST"
                }
            }
        },
    ]

def message_hash(msg):
    # Generate a unique hash based on speaker and text
    raw = (msg.get("speaker", "") + msg.get("text", "")).strip()
    return hashlib.sha256(raw.encode()).hexdigest()

async def poll_call_transcripts(call_id: str):
    seen_message_ids = set()
    logger.info(f"Starting polling for call_id={call_id}")
    
    # Store all messages for processing after call ends
    all_messages = []
    last_message_time = time.time()
    call_active = True

    try:
        while call_active:
            logger.info("Polling for new transcripts...")

            url = f"https://api.ultravox.ai/api/calls/{call_id}/messages"
            headers = {"X-API-Key": ULTRAVOX_API_KEY}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                messages = data.get("results") or data.get("messages") or data

                if not isinstance(messages, list):
                    logger.warning(f"Unexpected message format: {type(messages)} - {messages}")
                    await asyncio.sleep(2)
                    continue

                new_messages = False
                for msg in messages:
                    msg_id = message_hash(msg)

                    if msg_id in seen_message_ids:
                        continue  # Skip duplicates

                    seen_message_ids.add(msg_id)
                    new_messages = True
                    last_message_time = time.time()
                    
                    # Store message for later processing
                    all_messages.append(msg)

                    speaker = msg.get("speaker", "unknown").capitalize()
                    text = msg.get("text", "").strip()

                    if speaker == "User":
                        print(f"User: {text}")
                    elif speaker == "Assistant":
                        print(f"Assistant: {text}")
                    else:
                        print(f"{speaker}: {text}")

                # If no new messages for 30 seconds, assume call ended
                if not new_messages and time.time() - last_message_time > 30:
                    logger.info("No new messages for 30 seconds. Assuming call ended.")
                    call_active = False
                    
            else:
                logger.warning(f"Failed to poll messages: {response.status_code} {response.text}")
                # If we can't poll for 60 seconds, assume call ended
                if time.time() - last_message_time > 60:
                    logger.info("Cannot poll messages for 60 seconds. Assuming call ended.")
                    call_active = False

            await asyncio.sleep(2)

        # Call has ended, process the transcript
        await process_call_transcript(all_messages, call_id)

    except Exception as e:
        logger.error(f"Error polling transcripts: {e}")
        # Try to process whatever messages we have
        await process_call_transcript(all_messages, call_id)

# async def process_call_transcript(messages, call_id):
#     """Process the call transcript with LLM and save customer data"""
#     if not messages:
#         logger.warning("No messages to process")
#         return
    
#     # Format transcript for LLM processing
#     transcript = "\n".join([
#         f"{msg.get('speaker', 'unknown').capitalize()}: {msg.get('text', '')}" 
#         for msg in messages
#     ])
    
#     logger.info(f"Processing transcript for call {call_id}")
    
#     # Extract customer info using LLM
#     customer_data = groq_client.extract_customer_info(transcript)
    
#     # Print to terminal
#     print("\n" + "="*50)
#     print("EXTRACTED CUSTOMER DATA:")
#     print(json.dumps(customer_data, indent=2))
#     print("="*50 + "\n")
    
#     # Add metadata
#     customer_data["call_id"] = call_id
#     customer_data["processed_at"] = datetime.now().isoformat()
    
#     # Save to JSON file
#     filename = f"customer_data_{call_id}.json"
#     with open(filename, 'w') as f:
#         json.dump(customer_data, f, indent=2)
    
#     logger.info(f"Customer data saved to {filename}")


async def process_call_transcript(messages, call_id):
    """Process the call transcript with LLM and save customer data"""
    if not messages:
        logger.warning("No messages to process")
        return
    
    # Format transcript for LLM processing
    transcript = "\n".join([
        f"{msg.get('speaker', 'unknown').capitalize()}: {msg.get('text', '')}" 
        for msg in messages
    ])
    
    logger.info(f"Processing transcript for call {call_id}")
    
    # Extract customer info using LLM
    customer_data = groq_client.extract_customer_info(transcript)
    
    # Print to terminal
    print("\n" + "="*50)
    print("EXTRACTED CUSTOMER DATA:")
    print(json.dumps(customer_data, indent=2))
    print("="*50 + "\n")
    
    # Add metadata
    customer_data["call_id"] = call_id
    customer_data["processed_at"] = datetime.now().isoformat()
    
    # Save to JSON file
    filename = f"customer_data_{call_id}.json"
    with open(filename, 'w') as f:
        json.dump(customer_data, f, indent=2)
    
    logger.info(f"Customer data saved to {filename}")
    
    # Send email if we have customer email
    customer_email = customer_data.get("email")
    if customer_email and customer_email != "null":
        send_customer_email(customer_data, customer_email)

# def send_customer_email(customer_data, customer_email):
#     """Send email to customer with their information"""
#     subject = "Thank you for your inquiry"
    
#     # Create HTML email body
#     body = f"""
#     <html>
#     <body>
#         <h2>Thank you for your interest!</h2>
#         <p>We've received your information and will contact you shortly.</p>
        
#         <h3>Your Details:</h3>
#         <ul>
#             <li><strong>Name:</strong> {customer_data.get('name', 'Not provided')}</li>
#             <li><strong>Email:</strong> {customer_data.get('email', 'Not provided')}</li>
#             <li><strong>Available Time:</strong> {customer_data.get('available_time', 'Not provided')}</li>
#             <li><strong>Zip Code:</strong> {customer_data.get('zip_code', 'Not provided')}</li>
#         </ul>
        
#         <p>We'll be in touch soon to discuss your needs.</p>
        
#         <br>
#         <p>Best regards,<br>Your Company Team</p>
#     </body>
#     </html>
#     """
    
#     # Send email to customer and CC yourself
#     email_sender.send_email(
#         to_email=customer_email,
#         subject=subject,
#         body=body,
#         cc_email=os.getenv("MY_EMAIL")  # CC yourself
#     )



@app.post("/voice")
async def handle_incoming_call(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = {
            "systemPrompt": SYSTEM_PROMPT,
            "model": "fixie-ai/ultravox",
            "voice": "Cassidy-English",
            "temperature": 0.3,
            "firstSpeaker": "FIRST_SPEAKER_AGENT",
            "medium": {"twilio": {}},
            "selectedTools": get_selected_tools(),
            "experimentalSettings": {"backgroundNoiseFilter": True}
        }

        response = requests.post(
            ULTRAVOX_API_URL,
            headers={"Content-Type": "application/json", "X-API-Key": ULTRAVOX_API_KEY},
            json=payload
        )
        response.raise_for_status()

        call_data = response.json()
        join_url = call_data.get("joinUrl")
        call_id = call_data.get("callId") or call_data.get("id")

        if not join_url or not call_id:
            raise Exception("Missing joinUrl or callId from Ultravox response.")

        logger.info(f"Ultravox call started. Join URL: {join_url}, Call ID: {call_id}")
        background_tasks.add_task(poll_call_transcripts, call_id)

        twiml = f"""
        <Response>
            <Connect>
                <Stream url="{join_url}">
                    <Parameter name="caller_id" value="from-fastapi" />
                    <Parameter name="voiceActivityEvents" value="true" />
                    <Parameter name="streamingStartBehavior" value="sendDigits" />
                </Stream>
            </Connect>
        </Response>
        """
        return Response(content=twiml.strip(), media_type="application/xml")

    except Exception as e:
        logger.error(f"Call setup failed: {e}")
        twiml = """
        <Response>
            <Say>Sorry, we could not process your call right now.</Say>
        </Response>
        """
        return Response(content=twiml.strip(), media_type="application/xml")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "port": PORT}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)