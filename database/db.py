import time
from services.supabase_client import supabase


# =========================
# GENERIC QUERY HELPERS (WITH RETRY & BULK SUPPORT)
# =========================
def _execute_with_retry(query_func, attempts=3, delay=0.5):
    last_ex = None
    for i in range(attempts):
        try:
            response = query_func().execute()
            return response.data
        except Exception as e:
            last_ex = e
            # Handle Windows non-blocking socket error (10035) or generic transient errors
            if "10035" in str(e) or "immediately" in str(e).lower():
                time.sleep(delay * (i + 1))
                continue
            # If it's a schema or data error, don't retry
            break
    
    # If we are here, all attempts failed
    print(f"[DB ERROR] Operation failed after {attempts} attempts: {last_ex}")
    return None

def select(table: str, filters: dict = None):
    def run():
        query = supabase.table(table).select("*")
        if filters:
            for key, value in filters.items():
                if value is not None:
                    if isinstance(value, list):
                        query = query.in_(key, value)
                    else:
                        query = query.eq(key, value)
        return query
    
    res = _execute_with_retry(run)
    return res if res is not None else []

def select_recent(table: str, filters: dict = None, order_by: str = "created_at", limit: int = 10):
    """Select recent records ordered by a column (descending) with a limit."""
    def run():
        query = supabase.table(table).select("*")
        if filters:
            for key, value in filters.items():
                if value is not None:
                    if isinstance(value, list):
                        query = query.in_(key, value)
                    else:
                        query = query.eq(key, value)
        query = query.order(order_by, desc=True).limit(limit)
        return query
    
    res = _execute_with_retry(run)
    return res if res is not None else []

def insert(table: str, data: dict):
    return _execute_with_retry(lambda: supabase.table(table).insert(data))

def update(table: str, data: dict, filters: dict):
    def run():
        query = supabase.table(table).update(data)
        for key, value in filters.items():
            if isinstance(value, list):
                query = query.in_(key, value)
            else:
                query = query.eq(key, value)
        return query
    return _execute_with_retry(run)

def delete(table: str, filters: dict):
    def run():
        query = supabase.table(table).delete()
        for key, value in filters.items():
            if isinstance(value, list):
                query = query.in_(key, value)
            else:
                query = query.eq(key, value)
        return query
    return _execute_with_retry(run)
