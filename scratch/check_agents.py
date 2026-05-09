from database.db import select
from core.state import state

# Mock state if needed
state.company_id = "56044736-c07a-4284-9005-926c48972b22" # Example ID from logs

print("--- AGENTS ---")
agents = select("agents", {"company_id": state.company_id})
for a in agents:
    print(f"ID: {a['id']}, Name: {a['name']}, Comm: {a.get('commission_percent')}")

print("\n--- PARTIES ---")
parties = select("parties", {"company_id": state.company_id})
for p in parties:
    print(f"ID: {p['id']}, Name: {p['name']}, Agent: {p.get('agent_id')}")

print("\n--- FINAL INVOICES ---")
invoices = select("final_invoices", {"company_id": state.company_id})
for i in invoices:
    print(f"Inv: {i['invoice_no']}, Party: {i['party_id']}, Agent: {i.get('agent_id')}, Net: {i['net_amount']}")
