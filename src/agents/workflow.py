import os
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step, Event
from llama_index.llms.openai import OpenAI
from llama_parse import LlamaParse
from pinecone import Pinecone
from supabase import create_client

# 1. Custom Events MUST inherit from the official LlamaIndex 'Event' class tool
class FileParsingEvent(Event):
    def __init__(self, vendor_data: dict):
        super().__init__()
        self.vendor_data = vendor_data

class ComplianceReviewEvent(Event):
    def __init__(self, parsed_text: str, vendor_data: dict):
        super().__init__()
        self.parsed_text = parsed_text
        self.vendor_data = vendor_data

# The Master Multi-Agent State Graph
class ContractReviewWorkflow(Workflow):

    @step
    async def process_new_ingestion(self, ev: StartEvent) -> FileParsingEvent:
        """Step 1: Receive raw data row from the Airbyte staging pipeline."""
        # Use ev.get() to safely grab parameters passed into the workflow run function
        vendor_name = ev.get("vendor_name")
        vendor_data = ev.get("vendor_data")
        print(f"Workflow event activated for vendor: {vendor_name}")
        return FileParsingEvent(vendor_data=vendor_data)

    @step
    async def document_parser_agent(self, ev: FileParsingEvent) -> ComplianceReviewEvent:
        """Step 2: Forward raw URLs out to LlamaParse markdown conversion."""
        print("Parsing vendor compliance documents via LlamaParse...")
        
        parser = LlamaParse(api_key=os.environ.get("LLAMAPARSE_API_KEY"), result_type="markdown")
        
        # Read the sample vendor contract file sitting in your repository
        parsed_docs = await parser.aparse_documents(["sample-docs/vendor_contract.pdf"])
        combined_text = "\n\n".join([doc.text for doc in parsed_docs])
        
        # Initialize Pinecone connection using modern v6 format syntax
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        index = pc.Index("vendor-contracts")
        # index.upsert(vectors=[...])
        
        return ComplianceReviewEvent(parsed_text=combined_text, vendor_data=ev.vendor_data)

    @step
    async def legal_and_security_agents(self, ev: ComplianceReviewEvent) -> StopEvent:
        """Step 3: Run LLM compliance review prompt and save logs back to Supabase."""
        print("Specialist agents conducting risk classifications...")
        llm = OpenAI(model="gpt-4o-mini")
        
        prompt = f"""
        Analyze the following text for corporate risks. 
        Vendor: {ev.vendor_data.get('vendor_name')}
        Document Text: {ev.parsed_text}
        
        Identify:
        1. Auto-renewal trap clauses or liability cap omissions.
        2. Missing security protocols (MFA or encryption-at-rest gaps).
        
        Return a clear business review memo.
        """
        
        response = await llm.acomplete(prompt)
        
        # Securely publish logs to your permanent Supabase database schema layer
        supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY"))
        supabase.table("review_findings").insert({
            "vendor_id": ev.vendor_data.get("vendor_id"),
            "summary_memo": response.text,
            "status": "pending_review"  # Sets up human-in-the-loop validation flag
        }).execute()
        
        return StopEvent(result="Multi-agent compliance workflow completed successfully!")
