import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.agents.workflow import ContractReviewWorkflow
from llama_index.core.workflow import StartEvent

async def main():
    workflow = ContractReviewWorkflow(timeout=120, verbose=True)
    result = await workflow.run(
        vendor_id="VEN-004",
        vendor_name="NorthStar Analytics",
        vendor_data={
            "department": "Data Processing",
            "contract_value": 30000,
            "data_access_level": "Medium",
            "document_url": "sample-docs/northstar-analytics-dpa.pdf",
            "document_type": "Data Processing Agreement"
        }
    )
    print("RESULT:", result)

asyncio.run(main())