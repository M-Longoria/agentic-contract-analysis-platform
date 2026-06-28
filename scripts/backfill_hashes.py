"""
One-time utility used to backfill document hashes for existing records
after introducing hash-based deduplication.
Not required for normal application execution.
"""

import os
import hashlib
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ["DB_URL"]


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def generate_hash(text: str) -> str:
    normalized = normalize(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


conn = psycopg.connect(DB_URL)
cur = conn.cursor()

# 1. pull all parsed docs
cur.execute("SELECT id, raw_markdown FROM parsed_documents")
rows = cur.fetchall()

updated = 0

# 2. update SAME table with hash
for doc_id, raw_markdown in rows:
    if not raw_markdown:
        continue

    content_hash = generate_hash(raw_markdown)

    cur.execute("""
        UPDATE parsed_documents
        SET content_hash = %s
        WHERE id = %s
    """, (content_hash, doc_id))

    updated += 1

conn.commit()
cur.close()
conn.close()

print(f"Backfill complete. Updated {updated} rows.")