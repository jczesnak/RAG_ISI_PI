import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL="postgresql+psycopg2://postgres:123123@localhost:5433/rag_project_db"
COLLECTION_NAME = "rag_documents"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M"
TEMP_UPLOAD_DIR = "temp_uploads"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200