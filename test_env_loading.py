# test_env_loading.py
from dotenv import load_dotenv
import os

load_dotenv()

print("DB_HOST:", repr(os.environ.get('DB_HOST')))
print("DB_PORT:", repr(os.environ.get('DB_PORT')))