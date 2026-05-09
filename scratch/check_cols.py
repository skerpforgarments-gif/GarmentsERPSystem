from database.db import select
from core.state import state

# Mock state
state.company_id = "f6e8c8a1-1c1c-4c9c-855e-fe913bedcd3d" # Try to find a valid one or just fetch all

def check():
    items = select("items")
    print(f"Items found: {len(items)}")
    if items:
        print(f"First item keys: {list(items[0].keys())}")
        print(f"First item type: {items[0].get('item_type')}")
    
    parties = select("parties")
    print(f"Parties found: {len(parties)}")
    if parties:
        print(f"First party keys: {list(parties[0].keys())}")
        print(f"First party type: {parties[0].get('party_type')}")

if __name__ == "__main__":
    check()
