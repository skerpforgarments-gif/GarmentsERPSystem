from services.supabase_client import supabase
from core.state import state

def inspect_ledger():
    print("Inspecting ledger_entries table...")
    try:
        # Try to get one row to see column names
        res = supabase.table("ledger_entries").select("*").limit(1).execute()
        if res.data:
            print("Columns found:", res.data[0].keys())
        else:
            print("No data in table, trying to get columns via RPC or empty select...")
            # Supabase doesn't easily give schema via client, but we can try to guess from common patterns or errors.
            # Let's try selecting a likely wrong column to see if it lists valid ones in the error (sometimes it does)
            res2 = supabase.table("ledger_entries").select("id").limit(1).execute()
            if res2.data:
                 print("Table exists, has 'id'.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_ledger()
