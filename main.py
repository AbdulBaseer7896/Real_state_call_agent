#### This code is trying seperate endpoints for both RAG'S i.e. jump passes and birthday party packages

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response
from contextlib import asynccontextmanager
from pydantic import BaseModel
import logging
import requests
import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from datetime import datetime
from typing import Optional
from prompt3 import SYSTEM_PROMPT # Main prompt imported
import hashlib

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ULTRAVOX_API_KEY = os.getenv("ULTRAVOX_API_KEY")
ULTRAVOX_API_URL = "https://api.ultravox.ai/api/calls"
PORT = int(os.getenv("PORT", 5050))
BASE_URL = os.getenv("BASE_URL", "https://3b37-203-101-190-34.ngrok-free.app")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

retriever = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global retriever, retriever_bday
    logger.info("Loading embeddings and FAISS index...")
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3", model_kwargs={"device": "cpu"})
    embeddings.embed_query("test")

    # For vectorstore of jump passes data
    vectorstore = FAISS.load_local("faiss_index_skyzone", embeddings, allow_dangerous_deserialization=True)
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5, "k_fetch": 200})
    print("Vectorstore for jump passes has been loaded...")

    # For vectorstore of birthday passes data
    vectorstore_bday = FAISS.load_local("faiss_index_birthday", embeddings,
                                        allow_dangerous_deserialization=True)
    retriever_bday = vectorstore_bday.as_retriever(search_type="similarity", search_kwargs={"k": 3, "k_fetch": 200})
    print("Vectorstore for birthday party packages has been loaded...")

    logger.info("Retrievers are ready.")
    yield

app = FastAPI(lifespan=lifespan)

class RAGRequest(BaseModel):
    query: str

@app.post("/ragSearchjump")
async def retrieve_and_answer(request: RAGRequest) -> dict:
    query = request.query
    try:
        docs = await retriever.ainvoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])

        prompt = f"""
        You are a helpful and friendly assistant for Skyzone, speaking in clear, conversational English.

        The user has asked about available jump passes.
        Use only the following context, which is structured data about jump passes, to answer their question.

        Do not use any outside knowledge. Only refer to what's in the context.

        Context:
        {context}

        Question: {query}

        Instructions:
        - Only mention passes that are relevant to the user’s question.
        - For each relevant pass, mention its name, who it’s for (age), when it's available (days and schedule), how long the jump time is, and the price.
        - If a pass is listed as available from "Monday to Sunday," it applies to every day, so include it regardless of the day asked.
        - If the context gives a start and end day (e.g., "Friday to Monday"), include the pass only if the user’s day falls within that range.
        - Speak naturally and concisely, like you're talking to a customer on the phone.
        - Avoid robotic repetition. Vary sentence structure.
        - Do not list blank or missing information.
        - If nothing matches, say that politely and offer to help find something else.
        """
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        result = {"result": response.choices[0].message.content}
        return result
    except Exception as e:
        return {"result": "Error searching for information."}

@app.post("/ragSearchbday")
async def retrieve_and_answer_bday(request: RAGRequest) -> dict:
    query = request.query
    try:
        docs = await retriever_bday.ainvoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        prompt = f"""
        You are a friendly assistant for Skyzone, a Trampoline Park company, speaking in clear, conversational English.
        The user has asked about available birthday party packages.
        Use only the following context, which is structured data about birthday party packages, to answer the user's questions.
        Do not use any outside knowledge, only use information available from the context.
        Context:
        {context}
        Question:
        {query}
        Instructions:
        - Only mention birthday packages that are relevant to the user's question.
        - For each birthday party package, mention the package name, the jump pass it should be scheduled with, the number of minimum jumpers, jump time, party room time, food and drinks, paper goods included, whether skysocks are included or not, dessert, guest of honor, outside food drinks, and what other perks are included, the price for the birthday party package, and the additional jumper price.
        - Speak naturally and concisely, like you're talking to a customer on the phone.
        - Avoid robotic repetition. Vary sentence structure.
        - Do not list blank or missing information.
        - If nothing matches, say that politely and offer to help find something else.
        """
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        result = {"result": response.choices[0].message.content}
        return result
    except Exception as e:
        return {"result": "Error searching for information."}

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
                    "baseUrlPattern": "https://3b37-203-101-190-34.ngrok-free.app/ragSearchjump",
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
                    "baseUrlPattern": "https://3b37-203-101-190-34.ngrok-free.app/getDateTime",
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
                    "baseUrlPattern": "https://3b37-203-101-190-34.ngrok-free.app/ragSearchbday",
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

    try:
        while True:
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
        payload = {
            "systemPrompt": SYSTEM_PROMPT,
            "model": "fixie-ai/ultravox",
            "voice": "Mark",
            "temperature": 0.3,
            "firstSpeaker": "FIRST_SPEAKER_AGENT",
            "medium": {"twilio": {}},
            "selectedTools": get_selected_tools()
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