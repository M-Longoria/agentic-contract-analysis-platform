from datetime import datetime, timezone


def log_agent_start(supabase, run_id, agent_name, input_data):
    """Logs when an agent starts running."""

    start_time = datetime.now(timezone.utc)

    record = supabase.table("agent_runs").insert({
        "vendor_id": run_id,
        "agent_name": agent_name,
        "status": "RUNNING",
        "input_data": input_data,
        "created_at": start_time.isoformat()
    }).execute()

    return record.data[0]["id"], start_time


# 👇 THIS GOES UNDER IT (same file, same indentation level)

async def run_agent(supabase, run_id, agent_name, agent_callable, input_data):
    """
    Standard wrapper for ALL agents.
    Gives you full observability.
    """

    log_id, start_time = log_agent_start(
        supabase,
        run_id,
        agent_name,
        input_data
    )

    try:
        result = await agent_callable()

        end_time = datetime.now(timezone.utc)
        runtime = (end_time - start_time).total_seconds()

        supabase.table("agent_runs").update({
            "status": "SUCCESS",
            "output_data": result,
            "completed_at": end_time.isoformat(),
            "runtime_seconds": runtime
        }).eq("id", log_id).execute()

        return result

    except Exception as e:
        end_time = datetime.now(timezone.utc)
        runtime = (end_time - start_time).total_seconds()

        supabase.table("agent_runs").update({
            "status": "FAILED",
            "error_message": str(e),
            "completed_at": end_time.isoformat(),
            "runtime_seconds": runtime
        }).eq("id", log_id).execute()

        raise e