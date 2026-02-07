import os
import uuid
from dotenv import load_dotenv

load_dotenv()

# App Configuration
HUB_URL = os.getenv("HUB_URL")
MACHINE_TOKEN = os.getenv("MACHINE")

# Binance Configuration
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Logging Configuration
GRAYLOG_HOST = os.getenv("GRAYLOG_HOST")
GRAYLOG_PORT = int(os.getenv("GRAYLOG_PORT", 0))

ID_FILE = ".unique_id"
ENV_UNIQUE_ID = os.getenv("UNIQUE_ID")

if os.path.exists(ID_FILE):
    with open(ID_FILE, "r") as f:
        LOCAL_UNIQUE_ID = f.read().strip()
else:
    LOCAL_UNIQUE_ID = str(uuid.uuid4())[:8]
    with open(ID_FILE, "w") as f:
        f.write(LOCAL_UNIQUE_ID)

UNIQUE_ID = ENV_UNIQUE_ID or LOCAL_UNIQUE_ID
