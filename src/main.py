import os
import uuid  # Formats native unique ID keys for your Supabase UUID columns
import asyncio
from supabase import create_client
from agents.workflow import ContractReviewWorkflow

async def poll_airbyte_staging_table():
    """Checks your new Airbyte staging table for raw records to process."""
    print("Backend boot sequence initiated. Listening for Airbyte sync batches...")
    
    # 1. Properly reads your administrative service role environment variable
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(supabase_url, supabase_key)
    
    while True:
        try:
            # Pull raw rows from the staging table that haven't been validated yet
            response = supabase.table("raw_airbyte_vendors").select("*").execute()
            records = response.data
            
            for row in records:
                # 2. Look at your production 'vendors' table by 'name' to check for existing records
                exists = supabase.table("vendors").select("id").eq("name", row.get("vendor_name")).execute()
                
                if not exists.data:
                    print(f"New raw data record detected from Airbyte: {row.get('vendor_name')}. Processing...")
                    
                    # Generate a fresh, valid UUID token string for your primary key
                    vendor_uuid = str(uuid.uuid4())
                    
                    # 3. Propagate the row securely into your precise production table columns
                    supabase.table("vendors").insert({
                        "id": vendor_uuid,
                        "name": row.get("vendor_name"),
                        "contact_email": row.get("business_owner"), # Maps business owner text to your contact_email column
                        "status": "pending_review"
                    }).execute()
                    
                    # 4. Boot up your lightweight LlamaIndex workflow graph
                    workflow = ContractReviewWorkflow(timeout=120, verbose=True)
                    result = await workflow.run(
                        vendor_id=vendor_uuid,
                        vendor_name=row.get("vendor_name"), 
                        vendor_data=row
                    )
                    print(result)
                    
        except Exception as e:
            print(f"Ingestion database check exception encountered: {e}")
            
        # Pause for 60 seconds before checking the database again to conserve system resources
        await asyncio.sleep(60)

if __name__ == "__main__":
    # Launch our lightweight background loop
    asyncio.run(poll_airbyte_staging_table())
