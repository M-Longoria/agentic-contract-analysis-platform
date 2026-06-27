import os
import uuid
import hashlib
from datetime import datetime, timezone

from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step
from llama_parse import LlamaParse
from pinecone import Pinecone
from supabase import create_client

from .events import FileParsingEvent, ComplianceReviewEvent
from src.observability.workflow_utils import start_agent_run, finish_agent_run


class ContractReviewWorkflow(Workflow):

    # =========================
    # STEP 1: INGESTION
    # =========================
    @step
    async def process_new_ingestion(self, ev: StartEvent) -> FileParsingEvent:

        print(f"Starting workflow for vendor: {ev.get('vendor_id')}")

        return FileParsingEvent(
            vendor_id=ev.get("vendor_id"),
            vendor_name=ev.get("vendor_name"),
            vendor_data=ev.get("vendor_data")
        )

    # =========================
    # STEP 2: DEDUP FIRST (NO PARSE UNLESS NEW)
    # =========================
    @step
    async def document_parser_agent(self, ev: FileParsingEvent) -> ComplianceReviewEvent:

        print("Running dedup-first ingestion pipeline...")

        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        )

        # -------------------------
        # HASH HELPERS
        # -------------------------
        def normalize(text: str) -> str:
            return " ".join(text.strip().lower().split())

        def generate_hash(text: str) -> str:
            return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()

        document_path = ev.vendor_data.get("document_url", "")
        if not document_path:
            raise ValueError("Missing document_url in vendor_data")

        # =========================================================
        # STEP 1: EARLY DEDUP (BEFORE ANY PARSING)
        # =========================================================
        input_hash = generate_hash(document_path)

        existing = (
            supabase.table("parsed_documents")
            .select("id")
            .eq("content_hash", input_hash)
            .execute()
        )

        if existing.data:
            print("Duplicate detected BEFORE parsing — skipping entirely")
            return StopEvent(result=f"Duplicate skipped: {input_hash}")

        # =========================================================
        # STEP 2: PARSE ONLY IF NEW
        # =========================================================
        print("No duplicate found — running LlamaParse...")

        parser = LlamaParse(
            api_key=os.environ["LLAMAPARSE_API_KEY"],
            result_type="markdown"
        )

        parsed_docs = await parser.aload_data([document_path])
        combined_text = "\n\n".join(doc.text for doc in parsed_docs)

        # =========================================================
        # STEP 3: CONTENT HASH (FINAL SAFETY CHECK)
        # =========================================================
        content_hash = generate_hash(combined_text)

        existing_final = (
            supabase.table("parsed_documents")
            .select("id")
            .eq("content_hash", content_hash)
            .execute()
        )

        if existing_final.data:
            print("Duplicate detected AFTER parsing — skipping ingestion")
            return StopEvent(result=f"Duplicate skipped: {content_hash}")

        # =========================================================
        # STEP 4: CHUNKING
        # =========================================================
        words = combined_text.split()
        chunk_size = 500
        overlap = 100

        chunks = []
        i = 0
        while i < len(words):
            chunks.append(" ".join(words[i:i + chunk_size]))
            i += chunk_size - overlap

        # =========================================================
        # STEP 5: EMBEDDINGS + PINECONE
        # =========================================================
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index = pc.Index("vendor-contracts")

        from sentence_transformers import SentenceTransformer
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        document_uuid = str(uuid.uuid4())

        vectors = []
        for i, chunk in enumerate(chunks):
            embedding = embedding_model.encode(chunk).tolist()

            vectors.append({
                "id": f"{document_uuid}-chunk-{i}",
                "values": embedding,
                "metadata": {
                    "vendor_id": ev.vendor_id,
                    "document_id": document_uuid,
                    "chunk_index": i
                }
            })

        index.upsert(vectors=vectors)

        # =========================================================
        # STEP 6: SUPABASE WRITE (CLEAN + CONSISTENT)
        # =========================================================
        supabase.table("documents").insert({
            "id": document_uuid,
            "vendor_id": ev.vendor_id,
            "file_name": document_path.split("/")[-1],
            "storage_path": document_path,
            "file_type": document_path.split(".")[-1].upper()
        }).execute()

        supabase.table("parsed_documents").insert({
            "id": str(uuid.uuid4()),
            "document_id": document_uuid,
            "content_hash": content_hash
        }).execute()

        # =========================================================
        # STEP 7: NEXT STEP
        # =========================================================
        return ComplianceReviewEvent(
            document_id=document_uuid,
            agent_run_id=str(uuid.uuid4()),
            parsed_text=combined_text,
            vendor_data=ev.vendor_data
        )

    # =========================
    # STEP 3: LEGAL + SECURITY
    # =========================
    @step
    async def legal_and_security_agents(self, ev: ComplianceReviewEvent) -> StopEvent:

        print("Running legal + security analysis...")

        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        )

        run_id, start_time = start_agent_run(
            supabase=supabase,
            vendor_id=ev.vendor_data.get("vendor_id", ev.document_id),
            agent_name="Legal & Security Agent",
            input_data={
                "document_id": ev.document_id,
                "preview": ev.parsed_text[:1000]
            }
        )

        try:
            from llama_index.llms.groq import Groq

            llm = Groq(
                model="llama-3.1-8b-instant",
                api_key=os.environ["GROQ_API_KEY"]
            )

            prompt = f"""
            Analyze contract risks:

            {ev.parsed_text}

            Focus on:
            - liability exposure
            - auto-renewal clauses
            - security gaps
            """

            response = await llm.acomplete(prompt)

            finding_uuid = str(uuid.uuid4())

            supabase.table("review_findings").insert({
                "id": finding_uuid,
                "document_id": ev.document_id,
                "agent_run_id": run_id,
                "finding_type": "contract_risk_analysis",
                "severity": "MEDIUM",
                "clause_text": "auto-analysis",
                "description": str(response),
                "recommendation": "Review contract risks"
            }).execute()

            finish_agent_run(
                supabase=supabase,
                run_id=run_id,
                status="SUCCESS",
                start_time=start_time,
                output_data={"finding_id": finding_uuid}
            )

            return StopEvent(result="Workflow completed successfully")

        except Exception as e:

            finish_agent_run(
                supabase=supabase,
                run_id=run_id,
                status="FAILED",
                start_time=start_time,
                error=e
            )

            raise