from services.supabase_client import supabase


# =========================
# GENERIC QUERY HELPERS (WITH DEBUGGING)
# =========================
def select(table: str, filters: dict = None):
    try:
        query = supabase.table(table).select("*")

        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)

        response = query.execute()
        return response.data
    except Exception as e:
        print(f"[DB ERROR] Select from {table} failed: {e}")
        return []


def insert(table: str, data: dict):
    try:
        response = supabase.table(table).insert(data).execute()
        return response.data
    except Exception as e:
        print(f"[DB ERROR] Insert into {table} failed: {e}")
        return None


def update(table: str, data: dict, filters: dict):
    try:
        query = supabase.table(table).update(data)

        for key, value in filters.items():
            query = query.eq(key, value)

        response = query.execute()
        return response.data
    except Exception as e:
        print(f"[DB ERROR] Update on {table} failed: {e}")
        return None


def delete(table: str, filters: dict):
    try:
        query = supabase.table(table).delete()

        for key, value in filters.items():
            query = query.eq(key, value)

        response = query.execute()
        return response.data
    except Exception as e:
        print(f"[DB ERROR] Delete from {table} failed: {e}")
        return None
