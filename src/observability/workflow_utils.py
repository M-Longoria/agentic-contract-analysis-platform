from datetime import datetime, timezone
import uuid


def start_agent_run(supabase, vendor_id, agent_name, input_data=None):
    start_time = datetime.now(timezone.utc)

    run_id = str(uuid.uuid4())

    supabase.table("agent_runs").insert({
        "id": run_id,
        "vendor_id": vendor_id,
        "agent_name": agent_name,
        "status": "RUNNING",
        "input_data": input_data,
        "started_at": start_time.isoformat()
    }).execute()

    return run_id, start_time

def finish_agent_run(
    supabase,
    run_id,
    status,
    start_time,
    output_data=None,
    error=None
):
    end_time = datetime.now(timezone.utc)

    runtime = (end_time - start_time).total_seconds()

    supabase.table("agent_runs").update({
        "status": status,
        "output_data": output_data,
        "error_message": str(error) if error else None,
        "completed_at": end_time.isoformat(),
        "runtime_seconds": runtime
    }).eq("id", run_id).execute()