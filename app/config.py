import os
import json
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)

class Config:
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")
    EMAIL_TO = os.getenv("EMAIL_TO")

    @staticmethod
    def load_products():
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        if not os.path.exists(config_path):
            return {"cep": "01001000", "products": []}
        with open(config_path, "r") as f:
            return json.load(f)
