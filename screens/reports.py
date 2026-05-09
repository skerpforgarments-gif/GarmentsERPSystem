import flet as ft
from datetime import date, timedelta
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select
from components.table import TableBuilder

REPORT_OPTIONS = [
    "1. Sales Details",
    "2. Party-wise Sales",
    "3. Item-wise Sales",
    "4. Agent-wise Sales (with Commission)",
    "5. Party Ledger",
    "6. Party-wise Outstanding",
    "7. Agent Ledger",
    "8. Agent-wise Outstanding",
    "9. Expense Ledger",
    "10. Expense Ledger Outstanding",
    "11. Purchase Order Details",
    "12. Cheque Issue Details"
]

class ReportsScreen(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 20

        self.tabs = ft.Tabs(
            selected_index=0,
            on_change=self.on_tab_change,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SUB,
            divider_color="#F0F0F0",
            tabs=[
                ft.Tab(text="Analytics Dashboard"),
                ft.Tab(text="Central Report Viewer"),
            ],
        )

        self.content_area = ft.Container(expand=True)

        self.content = ft.Column(
            controls=[
                ft.Text("Business Intelligence & Reports", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                self.tabs,
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                self.content_area
            ],
            expand=True
        )

    def did_mount(self):
        self.load_analytics()

    def on_tab_change(self, e):
        if self.tabs.selected_index == 0:
            self.load_analytics()
        else:
            self.load_central_viewer()
        if self.page: self.update()

    # =========================================================
    # 1. ANALYTICS DASHBOARD
    # =========================================================
    def load_analytics(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first", color="red")
            return

        invoices = select("final_invoices", {"company_id": state.company_id})
        orders = select("orders", {"company_id": state.company_id})
        ledger = select("ledger_entries", {"company_id": state.company_id})

        total_sales = sum(float(i.get("net_amount", 0) or 0) for i in invoices)
        pending_orders_count = sum(1 for o in orders if o.get("status") in ["Pending", "Partial"])
        
        total_debit = sum(float(l.get("debit", 0) or 0) for l in ledger)
        total_credit = sum(float(l.get("credit", 0) or 0) for l in ledger)
        net_outstanding = total_debit - total_credit

        self.content_area.content = ft.Column([
            ft.Text("Business Health Overview", size=18, weight="bold", color=AppColors.TEXT_HEADER),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT),
            ft.ResponsiveRow([
                ft.Container(self.build_card("Total Sales Invoiced", f"₹{total_sales:,.2f}", ft.icons.MONETIZATION_ON, AppColors.PRIMARY), col={"sm": 12, "md": 4}),
                ft.Container(self.build_card("Net Market Outstanding", f"₹{net_outstanding:,.2f}", ft.icons.ACCOUNT_BALANCE, AppColors.DANGER), col={"sm": 12, "md": 4}),
                ft.Container(self.build_card("Orders Left to Pack", str(pending_orders_count), ft.icons.INVENTORY, AppColors.WARNING), col={"sm": 12, "md": 4}),
            ], spacing=20)
        ])

    def build_card(self, title, value, icon, accent_color):
        return ft.Container(
            padding=24, bgcolor=AppColors.BG_CARD, border_radius=AppStyles.RADIUS,
            shadow=AppStyles.CARD_SHADOW, border=ft.border.all(1, "#F0F0F0"),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, color=accent_color, size=24),
                        bgcolor=ft.colors.with_opacity(0.1, accent_color),
                        padding=12, border_radius=12
                    ),
                ]),
                ft.Divider(height=15, color=ft.colors.TRANSPARENT),
                ft.Text(title.upper(), size=11, weight="bold", color=AppColors.TEXT_SUB, style=ft.TextStyle(letter_spacing=0.5)),
                ft.Text(value, size=28, weight="bold", color=AppColors.TEXT_HEADER),
            ], spacing=0)
        )

    # =========================================================
    # 2. CENTRAL REPORT VIEWER
    # =========================================================
    def load_central_viewer(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first", color="red")
            return

        # Filters
        self.report_dd = ft.Dropdown(
            label="Select Report", 
            options=[ft.dropdown.Option(r) for r in REPORT_OPTIONS],
            width=300,
            value=REPORT_OPTIONS[0],
            on_change=self.on_report_type_change,
            **AppStyles.get_input_style()
        )
        
        today = date.today()
        first_day = today.replace(day=1)
        self.from_date = ft.TextField(label="From Date (YYYY-MM-DD)", value=first_day.isoformat(), width=180, **AppStyles.get_input_style())
        self.to_date = ft.TextField(label="To Date (YYYY-MM-DD)", value=today.isoformat(), width=180, **AppStyles.get_input_style())
        
        self.entity_dd = ft.Dropdown(label="Select Party/Agent", width=250, visible=False, **AppStyles.get_input_style())
        
        self.generate_btn = ft.ElevatedButton("Generate Report", icon=ft.icons.PLAY_ARROW, bgcolor=AppColors.PRIMARY, color=ft.colors.WHITE, on_click=self.generate_report)
        self.print_btn = ft.OutlinedButton("Print PDF", icon=ft.icons.PRINT, disabled=True)

        self.report_container = ft.Container(expand=True)

        self.content_area.content = ft.Column([
            ft.Container(
                bgcolor=ft.colors.WHITE, padding=20, border_radius=8, border=ft.border.all(1, "#E2E8F0"),
                content=ft.Row([
                    self.report_dd, self.from_date, self.to_date, self.entity_dd,
                    self.generate_btn, self.print_btn
                ], wrap=True, alignment=ft.MainAxisAlignment.START, spacing=15)
            ),
            ft.Divider(height=10, color=ft.colors.TRANSPARENT),
            self.report_container
        ], expand=True)
        
        self.on_report_type_change(None)

    def on_report_type_change(self, e):
        # Show/Hide entity dropdown based on report type
        val = self.report_dd.value
        self.entity_dd.visible = False
        self.entity_dd.options = []
        
        if val in ["5. Party Ledger", "7. Agent Ledger", "9. Expense Ledger"]:
            self.entity_dd.visible = True
            
            if "Party" in val:
                self.entity_dd.label = "Select Party"
                data = select("parties", {"company_id": state.company_id})
            elif "Agent" in val:
                self.entity_dd.label = "Select Agent"
                data = select("agents", {"company_id": state.company_id})
            else:
                self.entity_dd.label = "Select Expense Ledger"
                data = select("expense_ledgers", {"company_id": state.company_id})
                
            self.entity_dd.options = [ft.dropdown.Option(str(d["id"]), d.get("name", d.get("ledger_name", "Unknown"))) for d in data]

        if self.page: self.update()

    # =========================================================
    # REPORT GENERATION ENGINE
    # =========================================================
    def generate_report(self, e):
        r_type = self.report_dd.value
        f_date = self.from_date.value
        t_date = self.to_date.value
        
        self.report_container.content = ft.ProgressRing()
        if self.page: self.update()

        try:
            if r_type == "1. Sales Details":
                self.run_sales_details(f_date, t_date)
            elif r_type == "2. Party-wise Sales":
                self.run_party_wise_sales(f_date, t_date)
            elif r_type == "3. Item-wise Sales":
                self.run_item_wise_sales(f_date, t_date)
            elif r_type == "4. Agent-wise Sales (with Commission)":
                self.run_agent_wise_sales(f_date, t_date)
            elif r_type == "5. Party Ledger":
                self.run_party_ledger(f_date, t_date)
            elif r_type == "6. Party-wise Outstanding":
                self.run_party_outstanding()
            elif r_type == "7. Agent Ledger":
                self.run_agent_ledger(f_date, t_date)
            elif r_type == "8. Agent-wise Outstanding":
                self.run_agent_outstanding()
            elif r_type == "9. Expense Ledger":
                self.run_expense_ledger(f_date, t_date)
            elif r_type == "10. Expense Ledger Outstanding":
                self.run_expense_outstanding()
            elif r_type == "11. Purchase Order Details":
                self.run_po_details(f_date, t_date)
            elif r_type == "12. Cheque Issue Details":
                self.run_cheque_details(f_date, t_date)
            else:
                self.report_container.content = ft.Text(f"Report '{r_type}' logic under construction.", color="orange")
        except Exception as ex:
            self.report_container.content = ft.Text(f"Error generating report: {ex}", color="red")
            
        self.print_btn.disabled = False
        if self.page: self.update()

    # =========================================================
    # INDIVIDUAL REPORT LOGIC
    # =========================================================
    def run_sales_details(self, fd, td):
        invoices = select("final_invoices", {"company_id": state.company_id})
        parties = {str(p["id"]): p["name"] for p in select("parties", {"company_id": state.company_id})}
        
        data = []
        for inv in invoices:
            dt = inv.get("invoice_date", "")
            if fd <= dt <= td:
                data.append({
                    "inv_no": inv.get("invoice_no"),
                    "date": dt,
                    "party": parties.get(str(inv.get("party_id")), "Unknown"),
                    "taxable": f"₹{float(inv.get('taxable_amount',0)):,.2f}",
                    "tax": f"₹{float(inv.get('total_tax',0)):,.2f}",
                    "net": f"₹{float(inv.get('net_amount',0)):,.2f}"
                })
        
        cols = [
            {"key": "inv_no", "label": "Inv No"},
            {"key": "date", "label": "Date"},
            {"key": "party", "label": "Party"},
            {"key": "taxable", "label": "Taxable Amt"},
            {"key": "tax", "label": "Tax Amt"},
            {"key": "net", "label": "Net Amount"},
        ]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["date"], reverse=True))

    def run_party_wise_sales(self, fd, td):
        invoices = select("final_invoices", {"company_id": state.company_id})
        parties = {str(p["id"]): p["name"] for p in select("parties", {"company_id": state.company_id})}
        
        agg = {}
        for inv in invoices:
            dt = inv.get("invoice_date", "")
            if fd <= dt <= td:
                pid = str(inv.get("party_id"))
                if pid not in agg:
                    agg[pid] = {"party": parties.get(pid, "Unknown"), "count": 0, "net": 0}
                agg[pid]["count"] += 1
                agg[pid]["net"] += float(inv.get("net_amount", 0))
                
        data = [{"party": v["party"], "count": str(v["count"]), "net": f"₹{v['net']:,.2f}", "_sort": v["net"]} for v in agg.values()]
        cols = [
            {"key": "party", "label": "Party Name"},
            {"key": "count", "label": "No. of Invoices"},
            {"key": "net", "label": "Total Sales Value"},
        ]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["_sort"], reverse=True))

    def run_item_wise_sales(self, fd, td):
        # We need to pull from order_items or invoice items.
        # Since we don't have an invoice_items table explicitly tracking sizes in DB yet (saved as JSON usually),
        # we will simulate it by querying orders and filtering by date.
        orders = select("orders", {"company_id": state.company_id})
        
        agg = {}
        for o in orders:
            dt = o.get("order_date", "")
            if fd <= dt <= td:
                for item in o.get("items", []):
                    iname = item.get("item_name", "Unknown")
                    if iname not in agg: agg[iname] = {"qty": 0, "value": 0}
                    agg[iname]["qty"] += int(item.get("qty", 0))
                    agg[iname]["value"] += float(item.get("amount", 0))
                    
        data = [{"item": k, "qty": str(v["qty"]), "val": f"₹{v['value']:,.2f}", "_sort": v["value"]} for k, v in agg.items()]
        cols = [{"key": "item", "label": "Item Name"}, {"key": "qty", "label": "Total Pcs Sold"}, {"key": "val", "label": "Total Value"}]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["_sort"], reverse=True))

    def run_agent_wise_sales(self, fd, td):
        invoices = select("final_invoices", {"company_id": state.company_id})
        parties = {str(p["id"]): {"name": p["name"], "agent_id": p.get("agent_id")} for p in select("parties", {"company_id": state.company_id})}
        agents = {str(a["id"]): {"name": a["name"], "comm": float(a.get("commission_percentage", 0))} for a in select("agents", {"company_id": state.company_id})}
        
        agg = {}
        for inv in invoices:
            dt = inv.get("invoice_date", "")
            if fd <= dt <= td:
                p_info = parties.get(str(inv.get("party_id")), {})
                # Use invoice agent if available, else party agent
                aid = str(inv.get("agent_id")) if inv.get("agent_id") else str(p_info.get("agent_id"))
                if aid == "None": aid = None
                
                a_info = agents.get(aid, {"name": "Direct/No Agent", "comm": 0})
                aname = a_info["name"]
                
                if aname not in agg: agg[aname] = {"sales": 0, "comm_pct": a_info["comm"], "comm_amt": 0}
                net = float(inv.get("net_amount", 0))
                agg[aname]["sales"] += net
                agg[aname]["comm_amt"] += net * (a_info["comm"] / 100)
                
        data = [{"agent": k, "sales": f"₹{v['sales']:,.2f}", "pct": f"{v['comm_pct']}%", "comm": f"₹{v['comm_amt']:,.2f}", "_sort": v["sales"]} for k, v in agg.items()]
        cols = [{"key": "agent", "label": "Agent Name"}, {"key": "sales", "label": "Total Sales"}, {"key": "pct", "label": "Comm %"}, {"key": "comm", "label": "Commission Earned"}]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["_sort"], reverse=True))

    def run_party_ledger(self, fd, td):
        pid = self.entity_dd.value
        if not pid:
            self.report_container.content = ft.Text("Please select a Party from the dropdown.", color="red")
            return
            
        entries = select("ledger_entries", {"company_id": state.company_id, "party_id": pid})
        data = []
        running_bal = 0
        for e in sorted(entries, key=lambda x: x.get("created_at", "")):
            dr = float(e.get("debit", 0) or 0)
            cr = float(e.get("credit", 0) or 0)
            running_bal += (dr - cr)
            data.append({
                "date": str(e.get("created_at", ""))[:10],
                "type": "Invoice" if dr > 0 else "Receipt",
                "dr": f"₹{dr:,.2f}" if dr > 0 else "",
                "cr": f"₹{cr:,.2f}" if cr > 0 else "",
                "bal": f"₹{running_bal:,.2f} {'Dr' if running_bal > 0 else 'Cr'}"
            })
            
        cols = [{"key": "date", "label": "Date"}, {"key": "type", "label": "Type"}, {"key": "dr", "label": "Debit (+)"}, {"key": "cr", "label": "Credit (-)"}, {"key": "bal", "label": "Balance"}]
        self.report_container.content = TableBuilder(cols, data)

    def run_party_outstanding(self):
        ledger = select("ledger_entries", {"company_id": state.company_id})
        parties = {str(p["id"]): p["name"] for p in select("parties", {"company_id": state.company_id})}
        invoices = select("final_invoices", {"company_id": state.company_id})

        balances = {}
        for entry in ledger:
            pid = str(entry.get("party_id"))
            if not entry.get("party_id") or pid not in parties: continue
            if pid not in balances: balances[pid] = {"party_name": parties.get(pid), "debit": 0, "credit": 0}
            balances[pid]["debit"] += float(entry.get("debit", 0) or 0)
            balances[pid]["credit"] += float(entry.get("credit", 0) or 0)

        # Summary rows
        summary_data = []
        for pid, v in balances.items():
            net = v["debit"] - v["credit"]
            if round(net, 2) != 0:
                summary_data.append({
                    "party": v["party_name"], "dr": f"\u20b9{v['debit']:,.2f}", "cr": f"\u20b9{v['credit']:,.2f}",
                    "net": f"\u20b9{abs(net):,.2f} {'Dr' if net > 0 else 'Cr'}", "_sort": net
                })
        
        summary_cols = [{"key": "party", "label": "Party Name"}, {"key": "dr", "label": "Total Dr"}, {"key": "cr", "label": "Total Cr"}, {"key": "net", "label": "Net Balance"}]
        summary_table = TableBuilder(summary_cols, sorted(summary_data, key=lambda x: x["_sort"], reverse=True))

        # Detail rows (bill-by-bill)
        detail_data = []
        for inv in invoices:
            pid = str(inv.get("party_id"))
            if pid not in parties: continue
            net_amt = float(inv.get("net_amount", 0))
            # Find receipts against this party
            detail_data.append({
                "party": parties.get(pid, "Unknown"),
                "inv_no": inv.get("invoice_no", "-"),
                "date": inv.get("invoice_date", "-"),
                "inv_amt": f"\u20b9{net_amt:,.2f}",
            })
        
        detail_cols = [{"key": "party", "label": "Party"}, {"key": "inv_no", "label": "Invoice No"}, {"key": "date", "label": "Date"}, {"key": "inv_amt", "label": "Invoice Amount"}]
        detail_table = TableBuilder(detail_cols, sorted(detail_data, key=lambda x: x["date"], reverse=True))

        self.report_container.content = ft.Column([
            ft.Text("Summary View", size=16, weight="bold", color=AppColors.TEXT_HEADER),
            summary_table,
            ft.Divider(height=20),
            ft.Text("Detail View (Bill-by-Bill)", size=16, weight="bold", color=AppColors.TEXT_HEADER),
            detail_table
        ], expand=True, scroll=ft.ScrollMode.AUTO)

    def run_agent_ledger(self, fd, td):
        aid = self.entity_dd.value
        if not aid:
            self.report_container.content = ft.Text("Please select an Agent from the dropdown.", color="red")
            return
            
        invoices = select("final_invoices", {"company_id": state.company_id})
        parties = {str(p["id"]): p for p in select("parties", {"company_id": state.company_id})}
        payments = select("payment_vouchers", {"company_id": state.company_id})
        agent_info = select("agents", {"id": aid})[0] if select("agents", {"id": aid}) else {"commission_percentage": 0}
        comm_pct = float(agent_info.get("commission_percentage", 0))

        data = []
        running_bal = 0
        
        # 1. Commissions Earned (from sales linked to this agent's parties)
        for inv in invoices:
            dt = inv.get("invoice_date", "")
            if fd <= dt <= td:
                pid = str(inv.get("party_id"))
                p_agent = str(inv.get("agent_id")) if inv.get("agent_id") else str(parties.get(pid, {}).get("agent_id"))
                if p_agent == aid:
                    net = float(inv.get("net_amount", 0))
                    comm = net * (comm_pct / 100)
                    running_bal += comm
                    data.append({
                        "date": dt,
                        "type": f"Comm (Inv {inv.get('invoice_no')})",
                        "dr": "",
                        "cr": f"₹{comm:,.2f}",
                        "bal": f"₹{running_bal:,.2f} Cr"
                    })
                    
        # 2. Commissions Paid (from payment vouchers where account_id = agent)
        for pv in payments:
            dt = pv.get("voucher_date", "")
            if fd <= dt <= td and str(pv.get("account_id")) == aid:
                amt = float(pv.get("amount", 0))
                running_bal -= amt
                data.append({
                    "date": dt,
                    "type": f"Payment ({pv.get('voucher_no')})",
                    "dr": f"₹{amt:,.2f}",
                    "cr": "",
                    "bal": f"₹{running_bal:,.2f} Cr"
                })
                
        cols = [{"key": "date", "label": "Date"}, {"key": "type", "label": "Particulars"}, {"key": "dr", "label": "Paid (Dr)"}, {"key": "cr", "label": "Earned (Cr)"}, {"key": "bal", "label": "Balance"}]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["date"]))

    def run_agent_outstanding(self):
        invoices = select("final_invoices", {"company_id": state.company_id})
        parties = {str(p["id"]): {"name": p["name"], "agent_id": str(p.get("agent_id"))} for p in select("parties", {"company_id": state.company_id})}
        agents = {str(a["id"]): {"name": a["name"], "comm_pct": float(a.get("commission_percentage", 0)), "earned": 0, "paid": 0} for a in select("agents", {"company_id": state.company_id})}
        payments = select("payment_vouchers", {"company_id": state.company_id})

        for inv in invoices:
            pid = str(inv.get("party_id"))
            aid = str(inv.get("agent_id")) if inv.get("agent_id") else str(parties.get(pid, {}).get("agent_id"))
            if aid in agents:
                agents[aid]["earned"] += float(inv.get("net_amount", 0)) * (agents[aid]["comm_pct"] / 100)
                
        for pv in payments:
            aid = str(pv.get("account_id"))
            if aid in agents:
                agents[aid]["paid"] += float(pv.get("amount", 0))

        # Summary
        summary_data = []
        for v in agents.values():
            net = v["earned"] - v["paid"]
            if round(net, 2) != 0:
                summary_data.append({
                    "agent": v["name"], "earned": f"\u20b9{v['earned']:,.2f}", "paid": f"\u20b9{v['paid']:,.2f}",
                    "net": f"\u20b9{net:,.2f} Cr", "_sort": net
                })
        
        summary_cols = [{"key": "agent", "label": "Agent Name"}, {"key": "earned", "label": "Total Earned (Cr)"}, {"key": "paid", "label": "Total Paid (Dr)"}, {"key": "net", "label": "Net Payable"}]
        summary_table = TableBuilder(summary_cols, sorted(summary_data, key=lambda x: x["_sort"], reverse=True))

        # Detail (invoice-by-invoice)
        detail_data = []
        for inv in invoices:
            pid = str(inv.get("party_id"))
            p_info = parties.get(pid, {})
            aid = str(inv.get("agent_id")) if inv.get("agent_id") else str(p_info.get("agent_id"))
            if aid in agents:
                net_amt = float(inv.get("net_amount", 0))
                comm = net_amt * (agents[aid]["comm_pct"] / 100)
                detail_data.append({
                    "agent": agents[aid]["name"], "inv": inv.get("invoice_no", "-"),
                    "party": p_info.get("name", "Unknown"), "amt": f"\u20b9{net_amt:,.2f}",
                    "comm": f"\u20b9{comm:,.2f}"
                })
        detail_cols = [{"key": "agent", "label": "Agent"}, {"key": "inv", "label": "Invoice"}, {"key": "party", "label": "Party"}, {"key": "amt", "label": "Sale Amt"}, {"key": "comm", "label": "Commission"}]
        detail_table = TableBuilder(detail_cols, detail_data)

        self.report_container.content = ft.Column([
            ft.Text("Summary View", size=16, weight="bold", color=AppColors.TEXT_HEADER),
            summary_table,
            ft.Divider(height=20),
            ft.Text("Detail View (Invoice-by-Invoice)", size=16, weight="bold", color=AppColors.TEXT_HEADER),
            detail_table
        ], expand=True, scroll=ft.ScrollMode.AUTO)

    def run_expense_ledger(self, fd, td):
        eid = self.entity_dd.value
        if not eid:
            self.report_container.content = ft.Text("Please select an Expense Ledger from the dropdown.", color="red")
            return
            
        payments = select("payment_vouchers", {"company_id": state.company_id})
        exp_ledgers = {str(e["id"]): e["name"] for e in select("expense_ledgers", {"company_id": state.company_id})}
        
        data = []
        running_total = 0
        for pv in sorted(payments, key=lambda x: x.get("voucher_date", "")):
            if str(pv.get("expense_id")) == eid:
                dt = pv.get("voucher_date", "")
                if fd <= dt <= td:
                    amt = float(pv.get("amount", 0))
                    running_total += amt
                    data.append({
                        "date": dt,
                        "voucher": pv.get("voucher_no", "-"),
                        "narration": pv.get("narration", "-"),
                        "amount": f"\u20b9{amt:,.2f}",
                        "running": f"\u20b9{running_total:,.2f}"
                    })
                
        cols = [{"key": "date", "label": "Date"}, {"key": "voucher", "label": "Voucher No"}, {"key": "narration", "label": "Narration"}, {"key": "amount", "label": "Amount"}, {"key": "running", "label": "Running Total"}]
        self.report_container.content = TableBuilder(cols, data)

    def run_expense_outstanding(self):
        payments = select("payment_vouchers", {"company_id": state.company_id})
        exp_ledgers = {str(e["id"]): e["name"] for e in select("expense_ledgers", {"company_id": state.company_id})}
        
        totals = {}
        for pv in payments:
            eid = str(pv.get("expense_id"))
            if eid in exp_ledgers:
                if eid not in totals: totals[eid] = {"name": exp_ledgers[eid], "total": 0, "count": 0}
                totals[eid]["total"] += float(pv.get("amount", 0))
                totals[eid]["count"] += 1
                
        data = [{"ledger": v["name"], "count": str(v["count"]), "total": f"\u20b9{v['total']:,.2f}", "_sort": v["total"]} for v in totals.values()]
        cols = [{"key": "ledger", "label": "Expense Ledger"}, {"key": "count", "label": "No. of Payments"}, {"key": "total", "label": "Total Spent"}]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["_sort"], reverse=True))

    def run_po_details(self, fd, td):
        pos = select("purchase_orders", {"company_id": state.company_id})
        parties = {str(p["id"]): p["name"] for p in select("parties", {"company_id": state.company_id})}
        data = []
        for po in pos:
            dt = po.get("po_date", "")
            if fd <= dt <= td:
                data.append({
                    "po": po.get("po_no"), "date": dt, "supplier": parties.get(str(po.get("supplier_id")), "Unknown"),
                    "pcs": str(po.get("total_pcs")), "amt": f"₹{float(po.get('total_amount', 0)):,.2f}"
                })
        cols = [{"key": "po", "label": "PO No"}, {"key": "date", "label": "Date"}, {"key": "supplier", "label": "Supplier"}, {"key": "pcs", "label": "Total Pcs"}, {"key": "amt", "label": "Amount"}]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["date"], reverse=True))

    def run_cheque_details(self, fd, td):
        pv = select("payment_vouchers", {"company_id": state.company_id})
        data = []
        for p in pv:
            dt = p.get("voucher_date", "")
            if fd <= dt <= td and p.get("mode", "").lower() == "cheque":
                data.append({
                    "vno": p.get("voucher_no"), "date": dt, "ref": p.get("ref_no", "-"),
                    "amt": f"₹{float(p.get('amount', 0)):,.2f}", "narration": p.get("narration", "-")
                })
        cols = [{"key": "vno", "label": "Voucher No"}, {"key": "date", "label": "Date"}, {"key": "ref", "label": "Cheque/Ref No"}, {"key": "amt", "label": "Amount"}, {"key": "narration", "label": "Remarks"}]
        self.report_container.content = TableBuilder(cols, sorted(data, key=lambda x: x["date"], reverse=True))
