import os
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step
from llama_index.core.llms import OpenAI
from llama_parse import LlamaParse
from pinecone import Pinecone
from supabase import create_client

# We define plain text "Events" to pass data between our specialist agents
class FileParsingEvent:
    def __init__(self, vendor_data):
        self.vendor_data = vendor_data

class ComplianceReviewEvent:
    def __init__(self, parsed_text, vendor_data):
        self.parsed_text = parsed_text
        self.vendor_data = vendor_data

# The main Multi-Agent compliance assembly line
class ContractReviewWorkflow(Workflow):

    @step
    async def process_new_ingestion(self, ev: StartEvent) -> FileParsingEvent:
        """Step 1: Receive raw data row pulled from your Airbyte staging table."""
        print(f"Workflow triggered for vendor: {ev.vendor_name}")
        return FileParsingEvent(vendor_data=ev.vendor_data)

    @step
    async def document_parser_agent(self, ev: FileParsingEvent) -> ComplianceReviewEvent:
        """Step 2: Take the document URL and pass it to LlamaParse."""
        print("Parsing vendor compliance documents via LlamaParse...")
        
        parser = LlamaParse(api_key=os.environ.get("LLAMAPARSE_API_KEY"), result_type="markdown")
        
        # LlamaParse securely reads the file and outputs clean markdown text strings
        # (For this portfolio layout, we pass our synthetic test files)
        parsed_docs = await parser.aparse_documents(["sample-docs/vendor_contract.pdf"])
        combined_text = "\n\n".join([doc.text for doc in parsed_docs])
        
        # Index the text chunks to Pinecone here for long-term audit lookup
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        index = pc.Index("contract-review-index")
        # index.upsert(vectors=[...])
        
        return ComplianceReviewEvent(parsed_text=combined_text, vendor_data=ev.vendor_data)

    @step
    async def legal_and_security_agents(self, ev: ComplianceReviewEvent) -> StopEvent:
        """Step 3: Run the AI risk evaluation loop and save findings to Supabase."""
        print("Specialist agents running risk classifications...")
        llm = OpenAI(model="gpt-4o-mini")
        
        # Prompting the LLM to act as your specialized risk inspectors
        prompt = f"""
        Analyze the following text for corporate risks. 
        Vendor: {ev.vendor_data['vendor_name']}
        Document Text: {ev.parsed_text}
        
        Identify:
        1. Auto-renewal trap clauses or liability cap omissions.
        2. Missing security protocols (MFA or encryption-at-rest gaps).
        
        Return a clear business review memo.
        """
        
        response = await llm.acomplete(prompt)
        
        # Save the finalized findings back into your locked-down production Supabase tables
        supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY"))
        supabase.table("review_findings").insert({
            "vendor_id": ev.vendor_data["vendor_id"],
            "summary_memo": response.text,
            "status": "pending_review"  # Human-in-the-loop checkpoint flag
        }).execute()
        
        return StopEvent(result="Multi-agent compliance workflow completed successfully!")
