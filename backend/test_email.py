import sys
import logging
from app.utils.email_service import send_smtp_email
from app.models.db import db
from flask import Flask

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

app = Flask(__name__)
# Just set enough environment to run standalone
from dotenv import load_dotenv
load_dotenv()

with app.app_context():
    res = send_smtp_email(
        to_email="pallavijadhav482@gmail.com",
        subject="Test connection",
        text_body="testing"
    )
    print("RESULT:", res)
