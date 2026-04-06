from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# 🔥 ОБЯЗАТЕЛЬНО
load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

print("MONGO URL:", MONGO_URL)  # можешь потом удалить

client = AsyncIOMotorClient(MONGO_URL)
db = client["Math_Tutor"]

users = db["users"]