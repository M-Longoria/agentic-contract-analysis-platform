import os
import asyncio
from supabase import create_client
from agents.workflow import ContractReviewWorkflow

async def poll_airbyte_staging_table():
    """Checks your new Airbyte staging table for raw records to process."""
    print("Backend boot sequence initiated. Listening for Airbyte sync batches...")
    
    supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY"))
    
    while True:
        # Pull raw rows from the staging table that haven't been validated yet
        response = supabase.table("raw_airbyte_vendors").select("*").execute()
        records = response.data
        
        for row in records:
            # Look at your production 'vendors' table to see if we processed them already
            exists = supabase.table("vendors").select("vendor_id").eq("vendor_id", row["vendor_id"]).execute()
            
            if not exists.data:
                print(f"New raw data record detected from Airbyte: {row['vendor_name']}. Processing...")
                
                # 1. Propagate the row securely into your clean production schemas
                supabase.table("vendors").insert({
                    "vendor_id": row["vendor_id"],
                    "vendor_name": row["vendor_name"],
                    "department": row["department"],
                    "business_owner": row["business_owner"]
                }).execute()
                
                # 2. Boot up your lightweight LlamaIndex workflow graph
                workflow = ContractReviewWorkflow(timeout=120, verbose=True)
                result = await workflow.run(
                    vendor_name=row["vendor_name"], 
                    vendor_data=row
                )
                print(result)
                
        # Pause for 60 seconds before checking the database again to conserve system resources
        await asyncio.sleep(60)

if __name__ == "__main__":
    # Launch our lightweight background loop
    asyncio.run(poll_airbyte_staging_table())
