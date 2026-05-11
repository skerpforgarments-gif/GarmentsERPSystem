from services.supabase_client import supabase

try:
    # Try to add missing columns to orders table
    print("Attempting to add missing columns to 'orders' table...")
    
    # Unfortunately, standard Supabase PostgREST doesn't allow ALTER TABLE.
    # We must use RPC if available, or just fix the code.
    
    # Let's try to see if we can get the table definition
    res = supabase.table("orders").select("*").limit(1).execute()
    if res.data:
        print("Existing columns in 'orders':", res.data[0].keys())
    else:
        print("Table 'orders' is empty or inaccessible.")
        
except Exception as e:
    print(f"Error checking schema: {e}")
