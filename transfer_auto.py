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
import hashlib
import json

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env config
ULTRAVOX_API_KEY = os.getenv("ULTRAVOX_API_KEY")
print("This is the key = ", ULTRAVOX_API_KEY)
ULTRAVOX_API_URL = "https://api.ultravox.ai/api/calls"
PORT = int(os.getenv("PORT", 4040))
BASE_URL = os.getenv("BASE_URL")
TransferNumber = os.getenv("TransferNumber", "1234")
print("this is the BASE URL = ", BASE_URL)

# Simplified system prompt
SYSTEM_PROMPT = """
You are Johnny Sins from Wise Choice Realty, a friendly voice assistant for real estate referrals.

Key responsibilities:
1. Greet callers with: "This is Johnny Sins from Wise Choice Realty, I just want to know do you accept residential buyers and sellers (referrals) for your real estate business?"
2. Explain our pay-per-close referral model
3. Schedule callbacks with business experts when needed
4. For human transfer requests: Say "I'd be happy to connect you with a representative. Please hold while I transfer your call." then use the transfer_to_human tool
5. Use available tools for date queries and specific information requests

Always maintain a friendly, professional tone.
"""

retriever = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App startup – no embeddings or retrievers to load.")
    yield

app = FastAPI(lifespan=lifespan)

class DateRequest(BaseModel):
    date: Optional[str] = None

def get_selected_tools():
    return [
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
                "modelToolName": "transfer_to_human",
                "description": "Transfer the call to a human representative.",
                "timeout": "10.0s",
                "dynamicParameters": [],
                "http": {
                    "baseUrlPattern": f"{BASE_URL}/transfer",
                    "httpMethod": "POST"
                }
            }
        }
    ]

@app.post("/transfer")
async def transfer_to_human():
    """
    Endpoint to transfer the call to a human representative
    """
    logger.info(f"Transferring call to human representative at {TransferNumber}")
    # TwiML to transfer the call
    twiml = f"""
    <Response>
        <Say>I'm transferring you to one of our representatives. Please hold.</Say>
        <Dial>{TransferNumber}</Dial>
    </Response>
    """
    
    return Response(content=twiml.strip(), media_type="application/xml")

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

def message_hash(msg):
    # Generate a unique hash based on speaker and text
    raw = (msg.get("speaker", "") + msg.get("text", "")).strip()
    return hashlib.sha256(raw.encode()).hexdigest()

async def poll_call_transcripts(call_id: str, call_sid: str):
    seen_message_ids = set()
    logger.info(f"Starting polling for call_id={call_id}")

    try:
        # Start a timer for 20 seconds
        start_time = datetime.now()
        
        while True:
            # Check if 20 seconds have passed
            if (datetime.now() - start_time).total_seconds() >= 20:
                logger.info("20 seconds have passed, initiating transfer")
                # Initiate transfer by making a request to Twilio to redirect the call
                from twilio.rest import Client
                
                # Get Twilio credentials from environment
                account_sid = os.getenv("TWILIO_ACCOUNT_SID")
                auth_token = os.getenv("TWILIO_AUTH_TOKEN")
                
                if account_sid and auth_token:
                    client = Client(account_sid, auth_token)
                    # Update the call to redirect to transfer endpoint
                    call = client.calls(call_sid).update(
                        twiml=f'<Response><Redirect method="POST">{BASE_URL}/transfer</Redirect></Response>'
                    )
                    logger.info(f"Transfer initiated for call SID: {call_sid}")
                else:
                    logger.error("Twilio credentials not found, cannot initiate transfer")
                
                break

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

                for msg in messages:
                    msg_id = message_hash(msg)

                    if msg_id in seen_message_ids:
                        continue  # Skip duplicates

                    seen_message_ids.add(msg_id)

                    speaker = msg.get("speaker", "unknown").capitalize()
                    text = msg.get("text", "").strip()

                    if speaker == "User":
                        print(f"User: {text}")
                    elif speaker == "Assistant":
                        print(f"Assistant: {text}")
                    else:
                        print(f"{speaker}: {text}")

            else:
                logger.warning(f"Failed to poll messages: {response.status_code} {response.text}")

            await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"Error polling transcripts: {e}")

@app.post("/voice")
async def handle_incoming_call(request: Request, background_tasks: BackgroundTasks):
    try:
        # Get form data from Twilio
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        
        logger.info(f"Incoming call from {from_number}, SID: {call_sid}")
        
        payload = {
            "systemPrompt": SYSTEM_PROMPT,
            "model": "fixie-ai/ultravox",
            "voice": "Cassidy-English",
            "temperature": 0.3,
            "firstSpeaker": "FIRST_SPEAKER_AGENT",
            "medium": {
                "twilio": {}
            },
            "selectedTools": get_selected_tools(),
            "experimentalSettings": {"backgroundNoiseFilter": True}
        }

        logger.info(f"Sending payload to Ultravox")

        response = requests.post(
            ULTRAVOX_API_URL,
            headers={"Content-Type": "application/json", "X-API-Key": ULTRAVOX_API_KEY},
            json=payload
        )
        
        # Get detailed error information if request fails
        if response.status_code != 200:
            logger.error(f"Ultravox API error: {response.status_code} - {response.text}")
            response.raise_for_status()
            
        call_data = response.json()
        join_url = call_data.get("joinUrl")
        call_id = call_data.get("callId") or call_data.get("id")

        logger.info(f"Ultravox response: {call_data}")

        if not join_url or not call_id:
            raise Exception(f"Ultravox missing joinUrl/callId: {call_data}")

        # Poll transcripts in the background with call_sid for potential transfer
        background_tasks.add_task(poll_call_transcripts, call_id, call_sid)

        # Proper TwiML for connecting to Ultravox
        twiml = f"""
        <Response>
            <Connect>
                <Stream url="{join_url}">
                    <Parameter name="caller_id" value="{from_number}" />
                    <Parameter name="voiceActivityEvents" value="true" />
                    <Parameter name="streamingStartBehavior" value="sendDigits" />
                </Stream>
            </Connect>
        </Response>
        """
        
        logger.info(f"Returning TwiML with join URL: {join_url}")
        return Response(content=twiml.strip(), media_type="application/xml")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response content: {e.response.text}")
    except Exception as e:
        logger.error(f"Call setup failed: {e}")
        
    # Fallback to direct human transfer if Ultravox fails
    fallback_twiml = f"""
    <Response>
        <Say>Thank you for calling Wise Choice Realty. Let me connect you with a representative.</Say>
        <Dial>{TransferNumber}</Dial>
    </Response>
    """
    return Response(content=fallback_twiml.strip(), media_type="application/xml")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "port": PORT}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)