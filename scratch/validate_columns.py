import re, os

schema = {
    "purchase_orders": ["id","company_id","po_no","po_date","supplier_id","agent_id","destination","transporter_id","remarks","freight","other_charges","total_pcs","total_amount","tax_per","net_amount","status","created_at"],
    "purchase_order_items": ["id","company_id","purchase_order_id","item_id","item_name","size_value","rate","qty_pieces","amount"],
    "purchase_invoices": ["id","company_id","purchase_order_id","invoice_no","invoice_date","supplier_id","agent_id","destination","transporter_id","order_by","order_thro","qty_type","lr_no","lr_date","freight_charges","remarks","total_pcs","total_amount","taxable_amount","tax_type","tax_per","cgst_amount","sgst_amount","igst_amount","round_off","net_amount","status","created_at"],
    "stock_ledger": ["id","company_id","entry_date","item_id","size_value","transaction_type","ref_type","ref_id","qty","rate","created_at"],
    "orders": ["id","company_id","order_no","order_date","is_completed","party_id","agent_id","transporter_id","destination","documents_by","price_list_id","price_type","order_by","order_thro","party_order_no","party_order_date","remarks","qty_type","no_of_cases","no_of_items","total_pcs","total_boxes","total_amount","tax_type","tax_per","vat_cst_amount","td_percent","td_amount","spd_percent","spd_amount","festival_percent","festival_amount","scd_percent","scd_amount","cd_percent","cd_amount","round_off","net_amount","status","created_at"],
    "order_items": ["id","company_id","order_id","item_id","item_name","size_value","rate","qty_pieces","qty_boxes","amount","discount_amount","gross_amount","tax_percent"],
    "packing_slips": ["id","company_id","slip_no","slip_year","slip_date","party_id","agent_id","transporter_id","destination","documents_by","price_list_id","price_type","party_order_no","party_order_date","order_by","order_thro","qty_type","compliments","total_order_cases","packed_cases","no_of_cases","prepared_by","checked_by","packed_by","barcode_type","export_to_word","tax_type","tax_per","no_of_items","total_pcs","total_boxes","total_amount","aftdis_amount","td_percent","td_amount","spd_percent","spd_amount","festival_percent","festival_amount","scd_percent","scd_amount","cd_percent","cd_amount","tax_amount","round_off","net_amount","bar_cod_percent","status","created_at"],
    "packing_slip_items": ["id","company_id","packing_slip_id","order_id","item_id","item_name","size_value","rate","qty_pieces","qty_boxes","amount"],
    "transport_invoices": ["id","company_id","invoice_no","invoice_year","invoice_date","party_ref_no","party_id","agent_id","transporter_id","destination","documents_by","price_list_id","price_type","packing_slip_no","order_by","order_thro","qty_type","party_order_date","barcode_laser","barcode_dot_matrix","barcode_transport","preparation_date","no_of_items","total_pcs","total_boxes","total_amount","gross_amount","td_percent","td_amount","spd_percent","spd_amount","festival_percent","festival_amount","scd_percent","scd_amount","cd_percent","cd_amount","tax_type","tax_per","gst_amount","tcs_amount","round_off","net_amount","lr_no","lr_date","case_no","no_case","tot_weight","charges","status","created_at"],
    "transport_invoice_items": ["id","company_id","transport_invoice_id","packing_slip_id","item_id","item_name","size_value","rate","qty_pieces","qty_boxes","amount"],
    "final_invoices": ["id","company_id","transport_invoice_id","invoice_no","invoice_date","party_id","agent_id","transporter_id","destination","documents_by","price_list_id","price_type","order_by","order_thro","party_order_no","party_order_date","qty_type","lr_no","lr_date","no_of_boxes","freight_charges","no_of_items","total_pcs","total_boxes","total_amount","gross_amount","td_percent","td_amount","spd_percent","spd_amount","festival_percent","festival_amount","scd_percent","scd_amount","cd_percent","cd_amount","taxable_amount","tax_type","tax_per","cgst_amount","sgst_amount","igst_amount","tcs_amount","round_off","net_amount","created_at"],
    "final_invoice_items": ["id","company_id","final_invoice_id","item_id","item_name","size_value","rate","qty_pieces","qty_boxes","amount"],
    "receipt_vouchers": ["id","company_id","voucher_no","voucher_date","party_id","agent_id","amount","mode","bank_id","narration","created_at"],
    "payment_vouchers": ["id","company_id","voucher_no","voucher_date","party_id","agent_id","expense_id","amount","mode","bank_id","narration","created_at"],
    "ledger_entries": ["id","company_id","entry_date","account_type","account_id","ref_type","ref_id","debit","credit","narration"],
    "parties": ["id","company_id","name","party_type","billing_address_line1","billing_address_line2","billing_address_line3","billing_city","billing_district","billing_state","billing_pincode","delivery_address_line1","delivery_address_line2","delivery_address_line3","delivery_city","delivery_district","delivery_state","delivery_pincode","code","phone","mobile","fax","email","gstin","cst_no","pan_no","bank_name","bank_account_no","bank_ifsc","agent_id","transporter_id","price_list_id","destination","courier_name","reference","documents_thro","order_by","order_thro","opening_balance","opn_bal_type","for_allowed","credit_days","credit_limit","price_type","tax_type","gst_percent","igst_percent","cgst_percent","sgst_percent","tcs_percent","cess_percent","rate_percent","tcs_applicable","discount_trade","discount_scheme","discount_scd","discount_cd","discount_festival","discount_order","remarks","is_approved","is_blocked","created_at"],
    "items": ["id","company_id","item_code","item_order","brand_name","variety","style","item_name","item_type","sizes","pcs_per_inner_box","boxes_per_outer_box","box_type","hsn_code","tax_id","tax_name","is_approved","is_blocked","reason","opening_stock","created_at"],
    "party_contacts": ["id","company_id","party_id","contact_person","designation","phone_no","cell"],
    "price_lists": ["id","company_id","list_name","effective_date","price_type","created_at"],
    "price_list_items": ["id","company_id","price_list_id","item_id","size_value","wholesale_rate","retail_rate","mrp_rate"],
    "companies": ["id","user_id","company_code","branch_code","name","address","gst_details","financial_period","created_at"],
    "transporters": ["id","company_id","name","address","gstin"],
    "agents": ["id","company_id","name","address","gstin","bank_name","bank_account","bank_ifsc","commission_percent"],
    "banks": ["id","company_id","name","account_holder","account_no","ifsc_code","branch","opening_balance"],
    "taxes": ["id","company_id","name","hsn_code","tax_type","cgst_percent","sgst_percent","igst_percent","tcs_percent","cess_percent","rate_percent"],
    "staff": ["id","company_id","name","designation","department","phone","address","salary"],
    "expense_ledgers": ["id","company_id","name","account_code","group_name","hsn_sac","opening_balance","opn_bal_type","tax_id","description"],
    "general_items": ["id","company_id","item_code","item_name","uom","hsn_code","tax_name","tax_id"],
    "settings": ["id","company_id","flow_type","financial_year_start","financial_year_end","invoice_prefix","order_prefix"],
}

insert_pat = re.compile(r'(?:insert|update)\s*\(\s*"(\w+)"\s*,\s*\{([^}]+)\}')
key_pat = re.compile(r'"(\w+)"')

issues = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'venv', '.venv', 'scratch')]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as fh:
                content = fh.read()
            for m in insert_pat.finditer(content):
                table = m.group(1)
                cols_str = m.group(2)
                cols = key_pat.findall(cols_str)
                if table in schema:
                    for c in cols:
                        if c not in schema[table]:
                            line_no = content[:m.start()].count('\n') + 1
                            issues.append(f'{path}:{line_no} -> {table}.{c} NOT IN SCHEMA')

if issues:
    print(f'COLUMN MISMATCHES ({len(issues)}):')
    for i in issues:
        print(f'  {i}')
else:
    print(f'All DB writes match the schema - CLEAN for deployment!')
