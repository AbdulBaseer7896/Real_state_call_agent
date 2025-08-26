from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

call = client.calls.create(
    to=os.getenv("DESTINATION_PHONE_NUMBER"),
    from_=os.getenv("TWILIO_PHONE_NUMBER"),
    url=f"{os.getenv('BASE_URL')}/voice"
)

print("Call SID:", call.sid)
