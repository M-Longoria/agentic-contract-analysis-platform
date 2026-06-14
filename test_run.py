import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.agents.workflow import ContractReviewWorkflow
from llama_index.core.workflow import StartEvent

async def main():
    workflow = ContractReviewWorkflow(timeout=120, verbose=True)
    result = await workflow.run(
        vendor_id="VEN-001",
        vendor_name="Acme Payroll Systems",
        vendor_data={
            "department": "People Operations",
            "contract_value": 85000,
            "data_access_level": "High",
            "document_url": "sample-docs/acme-payroll-msa.pdf",
            "document_type": "Master Services Agreement"
        }
    )
    print("RESULT:", result)

asyncio.run(main())