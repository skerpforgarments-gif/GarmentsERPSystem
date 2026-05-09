from database.db import select
comps = select("companies", {})
for c in comps:
    print(f"ID: {c['id']}, Name: {c['name']}")

if comps:
    cid = comps[0]['id']
    print(f"\nChecking data for Company: {cid}")
    print("--- AGENTS ---")
    print(select("agents", {"company_id": cid}))
    print("\n--- PARTIES ---")
    print(select("parties", {"company_id": cid}))
    print("\n--- FINAL INVOICES ---")
    print(select("final_invoices", {"company_id": cid}))
