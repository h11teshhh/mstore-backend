from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
if not MONGO_URL or not DB_NAME:
    raise ValueError("MONGO_URL and DB_NAME must be set in the environment variables.")

SECRET_KEY = "Ugw3gcbSKSUopK8OuWlG9Vqrr86y2rlVmvxzVC-rnd4"
ALGORITHM = "HS256"
