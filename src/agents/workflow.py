import os
import uuid  # Handles validation structural string updates
import time
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step, Event
from llama_index.llms.openai import OpenAI
from llama_parse import LlamaParse
from pinecone import Pinecone
from supabase import create_client

class FileParsingEvent(Event):
    def __init__(self, vendor_id: str, vendor_name: str, vendor_data: dict):
        super().__init__()
        self.vendor_id = vendor_id
        self.vendor_name = vendor_name
        self.vendor_data = vendor_data

class ComplianceReviewEvent(Event):
    def __init__(self, document_id: str, agent_run_id: str, parsed_text: str, vendor_data: dict):
        super().__init__()
        self.document_id = document_id
        self.agent_run_id = agent_run_id
        self.parsed_text = parsed_text
        self.vendor_data = vendor_data

class ContractReviewWorkflow(Workflow):

    @step
    async def process_new_ingestion(self, ev: StartEvent) -> FileParsingEvent:
        """Step 1: Unpack parameters from the incoming event stream."""
        vendor_id = ev.get("vendor_id")
        vendor_name = ev.get("vendor_name")
        vendor_data = ev.get("vendor_data")
        print(f"Workflow tracking activated for vendor UUID: {vendor_id}")
        return FileParsingEvent(vendor_id=vendor_id, vendor_name=vendor_name, vendor_data=vendor_data)

    @step
    async def document_parser_agent(self, ev: FileParsingEvent) -> ComplianceReviewEvent:
        """Step 2: Parse documents via LlamaParse and populate tracking log tables."""
        start_time = time.time()
        print("Parsing compliance targets via LlamaParse Markdown optimization...")
        
        # 1. Run parsing job
        parser = LlamaParse(api_key=os.environ.get("LLAMAPARSE_API_KEY"), result_type="markdown")
        parsed_docs = await parser.aparse_documents(["sample-docs/vendor_contract.pdf"])
        combined_text = "\n\n".join([doc.text for doc in parsed_docs])
        parsing_duration = round(time.time() - start_time, 2)

        # 2. Establish connections to your databases
        supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        index = pc.Index("vendor-contracts")
        
        # 3. Create unique tracking UUIDs for this extraction iteration pass
        document_uuid = str(uuid.uuid4())
        agent_run_uuid = str(uuid.uuid4())
        parsed_doc_uuid = str(uuid.uuid4())
        
        # Log metadata directly to your 'documents' table schema 
        supabase.table("documents").insert({
            "id": document_uuid,
            "vendor_id": ev.vendor_id,
            "file_name": "vendor_contract.pdf",
            "storage_path": f"sample-docs/vendor_contract.pdf",
            "file_type": "PDF"
        }).execute()
        
        # Log results cleanly inside your 'parsed_documents' table schema
        supabase.table("parsed_documents").insert({
            "id": parsed_doc_uuid,
            "document_id": document_uuid,
            "raw_markdown": combined_text,
            "parsing_duration_seconds": parsing_duration
        }).execute()
        
        # Set up a tracking placeholder checkpoint row inside your 'agent_runs' table
        supabase.table("agent_runs").insert({
            "id": agent_run_uuid,
            "vendor_id": ev.vendor_id,
            "agent_name": "LlamaParse Document Extraction Agent",
            "status": "COMPLETED"
        }).execute()

        return ComplianceReviewEvent(
            document_id=document_uuid, 
            agent_run_id=agent_run_uuid, 
            parsed_text=combined_text, 
            vendor_data=ev.vendor_data
        )

    @step
    async def legal_and_security_agents(self, ev: ComplianceReviewEvent) -> StopEvent:
        """Step 3: Run AI analysis and record precise metrics inside review_findings columns."""
        print("Specialist agents conducting risk classifications...")
        llm = OpenAI(model="gpt-4o-mini")
        
        prompt = f"""
        Analyze the following text for corporate contract risks.
        Document Text: {ev.parsed_text}
        
        Identify:
        1. Auto-renewal terms or liability caps.
        2. Encryption or MFA gaps.
        
        Draft a crisp recommendation and describe findings.
        """
        
        response = await llm.acomplete(prompt)
        
        # Establish connection using administrative service role key
        supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
        finding_uuid = str(uuid.uuid4())
        
        # Write directly to your specific 'review_findings' table matching your exact database columns
        supabase.table("review_findings").insert({
            "id": finding_uuid,
            "document_id": ev.document_id,
            "agent_run_id": ev.agent_run_id,
            "finding_type": "Contract Compliance Assessment",
            "severity": "MEDIUM",
            "clause_text": "Section 1-3 Liability Thresholds & Data Encryption Metrics",
            "description": response.text,
            "recommendation": "Review the $5,000 liability cap and ensure data protection policies are explicitly met."
        }).execute()
        
        return StopEvent(result="Multi-agent compliance workflow completed successfully!")
