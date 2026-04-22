

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DROP TABLE IF EXISTS ledger_entries CASCADE;
DROP TABLE IF EXISTS payment_vouchers CASCADE;
DROP TABLE IF EXISTS receipt_vouchers CASCADE;
DROP TABLE IF EXISTS final_invoice_items CASCADE;
DROP TABLE IF EXISTS final_invoices CASCADE;
DROP TABLE IF EXISTS transport_invoice_items CASCADE;
DROP TABLE IF EXISTS transport_invoices CASCADE;
DROP TABLE IF EXISTS packing_slip_items CASCADE;
DROP TABLE IF EXISTS packing_slips CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS price_list_items CASCADE;
DROP TABLE IF EXISTS price_lists CASCADE;
DROP TABLE IF EXISTS party_contacts CASCADE;
DROP TABLE IF EXISTS parties CASCADE;
DROP TABLE IF EXISTS items CASCADE;
DROP TABLE IF EXISTS general_items CASCADE;
DROP TABLE IF EXISTS expense_ledgers CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS taxes CASCADE;
DROP TABLE IF EXISTS banks CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
DROP TABLE IF EXISTS transporters CASCADE;
DROP TABLE IF EXISTS companies CASCADE;

DROP FUNCTION IF EXISTS public.get_user_company_id CASCADE;

-- =========================================================
-- 1. SAAS CORE
-- =========================================================
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    company_code    TEXT,
    branch_code     TEXT,
    name            TEXT NOT NULL,
    address         TEXT,
    gst_details     TEXT,
    financial_period TEXT,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.get_user_company_id()
RETURNS uuid LANGUAGE sql SECURITY DEFINER
SET search_path = public STABLE AS $$
  SELECT id FROM public.companies WHERE user_id = auth.uid() LIMIT 1;
$$;

-- =========================================================
-- 2. SIMPLE MASTERS
-- =========================================================
CREATE TABLE transporters (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    address     TEXT,
    gstin       TEXT
);

CREATE TABLE agents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    address             TEXT,
    gstin               TEXT,
    bank_name           TEXT,
    bank_account        TEXT,
    bank_ifsc           TEXT,
    commission_percent  NUMERIC(5,2) DEFAULT 0
);

CREATE TABLE banks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        TEXT NOT NULL
);

CREATE TABLE taxes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    tax_type    TEXT,   -- CGST / SGST / IGST / TCS
    rate_percent NUMERIC(5,2) DEFAULT 0
);

CREATE TABLE staff (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    designation TEXT
);

CREATE TABLE expense_ledgers (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        TEXT NOT NULL
);

CREATE TABLE general_items (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_code   TEXT,
    item_name   TEXT NOT NULL,
    uom         TEXT,
    tax_id      UUID REFERENCES taxes(id)
);

-- =========================================================
-- 3. ITEM MASTER
-- =========================================================
CREATE TABLE items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_code           TEXT NOT NULL,
    item_order          INTEGER DEFAULT 1,
    brand_name          TEXT,
    variety             TEXT,
    style               TEXT,
    item_name           TEXT NOT NULL,
    sizes               TEXT[] NOT NULL DEFAULT '{}',
    pcs_per_inner_box   INTEGER DEFAULT 1,
    boxes_per_outer_box INTEGER DEFAULT 1,
    box_type            TEXT DEFAULT 'Single Box Pack',
    hsn_code            TEXT,
    is_approved         BOOLEAN DEFAULT TRUE,
    is_blocked          BOOLEAN DEFAULT FALSE,
    reason              TEXT,
    opening_stock       JSONB DEFAULT '{}'  -- {"80": 100, "85": 200, ...}
);

-- =========================================================
-- 4. PRICE LIST MASTER
-- =========================================================
CREATE TABLE price_lists (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    list_name       TEXT NOT NULL,
    effective_date  DATE,
    price_type      TEXT DEFAULT 'Wholesale',
    created_at      TIMESTAMP DEFAULT now()
);

-- Size-wise rate pivot table
CREATE TABLE price_list_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    price_list_id   UUID NOT NULL REFERENCES price_lists(id) ON DELETE CASCADE,
    item_id         UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    size_value      TEXT NOT NULL,
    wholesale_rate  NUMERIC(10,2) DEFAULT 0,
    retail_rate     NUMERIC(10,2) DEFAULT 0,
    mrp_rate        NUMERIC(10,2) DEFAULT 0,
    UNIQUE(price_list_id, item_id, size_value)
);

-- =========================================================
-- 5. PARTY MASTER (30+ fields from screenshot)
-- =========================================================
CREATE TABLE parties (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Basic Info
    name                TEXT NOT NULL,
    address_line1       TEXT,
    address_line2       TEXT,
    address_line3       TEXT,
    city                TEXT,
    district            TEXT,
    state               TEXT,
    pincode             TEXT,
    -- Communication
    code                TEXT,
    phone               TEXT,
    mobile              TEXT,
    fax                 TEXT,
    email               TEXT,
    -- Tax IDs
    gstin               TEXT,
    cst_no              TEXT,
    pan_no              TEXT,
    -- Bank Details (Requested in Requirement Doc)
    bank_name           TEXT,
    bank_account_no     TEXT,
    bank_ifsc           TEXT,
    -- Linked Masters
    agent_id            UUID REFERENCES agents(id),
    transporter_id      UUID REFERENCES transporters(id),
    price_list_id       UUID REFERENCES price_lists(id),
    -- Logistics
    destination         TEXT,
    courier_name        TEXT,
    reference           TEXT,
    documents_thro      TEXT DEFAULT 'Direct', -- Direct / Bank
    order_by            TEXT,
    order_thro          TEXT DEFAULT 'DIRECT',
    -- Financial Terms
    opening_balance     NUMERIC(12,2) DEFAULT 0,
    opn_bal_type        TEXT DEFAULT 'DEBIT',  -- DEBIT / CREDIT
    for_allowed         BOOLEAN DEFAULT TRUE,
    credit_days         INTEGER DEFAULT 0,
    credit_limit        NUMERIC(12,2) DEFAULT 0,
    price_type          TEXT DEFAULT 'Wholesale',  -- Wholesale / Retail / MRP
    -- Tax Settings
    tax_type            TEXT DEFAULT 'GST',   -- GST / TCS / IGST
    gst_percent         NUMERIC(5,2) DEFAULT 0,
    igst_percent        NUMERIC(5,2) DEFAULT 0,
    tcs_applicable      BOOLEAN DEFAULT FALSE,
    -- Discount Structure (%)
    discount_trade      NUMERIC(5,2) DEFAULT 0,   -- TD
    discount_scheme     NUMERIC(5,2) DEFAULT 0,   -- SPD
    discount_scd        NUMERIC(5,2) DEFAULT 0,   -- SCD
    discount_cd         NUMERIC(5,2) DEFAULT 0,   -- CD
    -- Remarks & Status
    remarks             TEXT,
    is_approved         BOOLEAN DEFAULT TRUE,
    is_blocked          BOOLEAN DEFAULT FALSE
);

-- Party Contacts Sub-Table (screenshot: grid at bottom of party master)
CREATE TABLE party_contacts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id        UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    contact_person  TEXT,
    designation     TEXT,
    phone_no        TEXT,
    cell            TEXT
);

-- =========================================================
-- 6. ORDER ENTRY
-- =========================================================
CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Header
    order_no            TEXT NOT NULL,
    order_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    is_completed        BOOLEAN DEFAULT FALSE,
    party_id            UUID NOT NULL REFERENCES parties(id),
    agent_id            UUID REFERENCES agents(id),
    transporter_id      UUID REFERENCES transporters(id),
    destination         TEXT,
    documents_by        TEXT DEFAULT 'Direct',
    price_list_id       UUID REFERENCES price_lists(id),
    price_type          TEXT DEFAULT 'Wholesale',
    order_by            TEXT,
    order_thro          TEXT DEFAULT 'DIRECT',
    party_order_no      TEXT,
    party_order_date    DATE,
    remarks             TEXT,
    qty_type            TEXT DEFAULT 'Pieces',  -- Pieces / Boxes
    no_of_cases         INTEGER DEFAULT 0,
    -- Footer Totals
    no_of_items         INTEGER DEFAULT 0,
    total_pcs           INTEGER DEFAULT 0,
    total_boxes         NUMERIC(10,2) DEFAULT 0,
    total_amount        NUMERIC(12,2) DEFAULT 0,
    -- Tax & Discount Footer
    tax_type            TEXT DEFAULT 'IGST',
    tax_per             NUMERIC(5,2) DEFAULT 5,
    vat_cst_amount      NUMERIC(12,2) DEFAULT 0,
    td_percent          NUMERIC(5,2) DEFAULT 0,
    td_amount           NUMERIC(12,2) DEFAULT 0,
    spd_percent         NUMERIC(5,2) DEFAULT 0,
    spd_amount          NUMERIC(12,2) DEFAULT 0,
    scd_percent         NUMERIC(5,2) DEFAULT 0,
    cd_percent          NUMERIC(5,2) DEFAULT 0,
    cd_amount           NUMERIC(12,2) DEFAULT 0,
    round_off           NUMERIC(10,2) DEFAULT 0,
    net_amount          NUMERIC(12,2) DEFAULT 0,
    -- Status
    status              TEXT DEFAULT 'Pending'  -- Pending, Packed, Invoiced
);

CREATE TABLE order_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    order_id        UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_id         UUID NOT NULL REFERENCES items(id),
    size_value      TEXT NOT NULL,
    rate            NUMERIC(10,2) DEFAULT 0,
    qty_pieces      INTEGER DEFAULT 0,
    qty_boxes       NUMERIC(10,2) DEFAULT 0,
    amount          NUMERIC(12,2) DEFAULT 0,
    discount_amount NUMERIC(12,2) DEFAULT 0,
    gross_amount    NUMERIC(12,2) DEFAULT 0,
    tax_percent     NUMERIC(5,2) DEFAULT 0
);

-- =========================================================
-- 7. PACKING SLIP
-- =========================================================
CREATE TABLE packing_slips (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Header
    slip_no             TEXT NOT NULL,
    slip_year           TEXT,
    slip_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    party_id            UUID NOT NULL REFERENCES parties(id),
    agent_id            UUID REFERENCES agents(id),
    transporter_id      UUID REFERENCES transporters(id),
    destination         TEXT,
    documents_by        TEXT DEFAULT 'Direct',
    price_list_id       UUID REFERENCES price_lists(id),
    price_type          TEXT DEFAULT 'Wholesale',
    party_order_no      TEXT,
    party_order_date    DATE,
    order_by            TEXT,
    order_thro          TEXT DEFAULT 'DIRECT',
    qty_type            TEXT DEFAULT 'Pieces',
    compliments         TEXT,
    -- Case Tracking (from screenshot)
    total_order_cases   INTEGER DEFAULT 0,
    packed_cases        INTEGER DEFAULT 0,
    no_of_cases         INTEGER DEFAULT 0,
    -- Prep Details (from screenshot)
    prepared_by         TEXT,
    checked_by          TEXT,
    packed_by           TEXT,
    barcode_type        TEXT DEFAULT 'Laser',  -- Laser / Dot Matrix
    export_to_word      BOOLEAN DEFAULT FALSE,
    -- Tax
    tax_type            TEXT DEFAULT 'IGST',
    tax_per             NUMERIC(5,2) DEFAULT 5,
    -- Footer Totals
    no_of_items         INTEGER DEFAULT 0,
    total_pcs           INTEGER DEFAULT 0,
    total_boxes         NUMERIC(10,2) DEFAULT 0,
    total_amount        NUMERIC(12,2) DEFAULT 0,
    aftdis_amount       NUMERIC(12,2) DEFAULT 0,
    td_percent          NUMERIC(5,2) DEFAULT 0,
    td_amount           NUMERIC(12,2) DEFAULT 0,
    spd_percent         NUMERIC(5,2) DEFAULT 0,
    spd_amount          NUMERIC(12,2) DEFAULT 0,
    scd_percent         NUMERIC(5,2) DEFAULT 0,
    tax_amount          NUMERIC(12,2) DEFAULT 0,
    round_off           NUMERIC(10,2) DEFAULT 0,
    net_amount          NUMERIC(12,2) DEFAULT 0,
    bar_cod_percent     NUMERIC(5,2) DEFAULT 0,
    -- Status
    status              TEXT DEFAULT 'Unbilled'  -- Unbilled / Billed
);

CREATE TABLE packing_slip_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    packing_slip_id     UUID NOT NULL REFERENCES packing_slips(id) ON DELETE CASCADE,
    order_id            UUID REFERENCES orders(id),
    item_id             UUID NOT NULL REFERENCES items(id),
    size_value          TEXT NOT NULL,
    rate                NUMERIC(10,2) DEFAULT 0,
    qty_pieces          INTEGER DEFAULT 0,
    qty_boxes           NUMERIC(10,2) DEFAULT 0,
    amount              NUMERIC(12,2) DEFAULT 0
);

-- =========================================================
-- 8. TRANSPORT INVOICE (Original Invoice in screenshots)
-- =========================================================
CREATE TABLE transport_invoices (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Header
    invoice_no          TEXT NOT NULL,
    invoice_year        TEXT,
    invoice_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    party_ref_no        TEXT,
    party_id            UUID NOT NULL REFERENCES parties(id),
    agent_id            UUID REFERENCES agents(id),
    transporter_id      UUID REFERENCES transporters(id),
    destination         TEXT,
    documents_by        TEXT DEFAULT 'Direct',
    price_list_id       UUID REFERENCES price_lists(id),
    price_type          TEXT DEFAULT 'Wholesale',
    packing_slip_no     TEXT,
    order_by            TEXT,
    order_thro          TEXT DEFAULT 'DIRECT',
    qty_type            TEXT DEFAULT 'Pieces',
    party_order_date    DATE,
    -- Print Options
    barcode_laser           BOOLEAN DEFAULT TRUE,
    barcode_dot_matrix      BOOLEAN DEFAULT FALSE,
    barcode_transport       BOOLEAN DEFAULT FALSE,
    preparation_date        DATE,
    -- Footer Totals
    no_of_items         INTEGER DEFAULT 0,
    total_pcs           INTEGER DEFAULT 0,
    total_boxes         NUMERIC(10,2) DEFAULT 0,
    total_amount        NUMERIC(12,2) DEFAULT 0,
    gross_amount        NUMERIC(12,2) DEFAULT 0,
    -- Discount Stacking (sequential per screenshot)
    less_sd_percent     NUMERIC(5,2) DEFAULT 0,   -- Special Discount
    less_sd_amount      NUMERIC(12,2) DEFAULT 0,
    less_trade_percent  NUMERIC(5,2) DEFAULT 0,   -- Trade Discount (21%)
    less_trade_amount   NUMERIC(12,2) DEFAULT 0,
    less_cash_percent   NUMERIC(5,2) DEFAULT 0,   -- Cash Discount (2%)
    less_cash_amount    NUMERIC(12,2) DEFAULT 0,
    -- Tax
    tax_type            TEXT DEFAULT 'IGST',
    tax_per             NUMERIC(5,2) DEFAULT 5,
    gst_amount          NUMERIC(12,2) DEFAULT 0,
    tcs_amount          NUMERIC(12,2) DEFAULT 0,
    -- Bottom Summary
    round_off           NUMERIC(10,2) DEFAULT 0,
    net_amount          NUMERIC(12,2) DEFAULT 0,
    -- LR Details (at the bottom of screenshot)
    lr_no               TEXT,
    lr_date             DATE,
    case_no             TEXT,
    no_case             INTEGER DEFAULT 0,
    tot_weight          NUMERIC(10,2) DEFAULT 0,
    charges             NUMERIC(12,2) DEFAULT 0,
    -- Status
    status              TEXT DEFAULT 'Unbilled'  -- Unbilled / Invoiced
);

CREATE TABLE transport_invoice_items (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    transport_invoice_id    UUID NOT NULL REFERENCES transport_invoices(id) ON DELETE CASCADE,
    packing_slip_id         UUID REFERENCES packing_slips(id),
    item_id                 UUID NOT NULL REFERENCES items(id),
    size_value              TEXT NOT NULL,
    rate                    NUMERIC(10,2) DEFAULT 0,
    qty_pieces              INTEGER DEFAULT 0,
    qty_boxes               NUMERIC(10,2) DEFAULT 0,
    amount                  NUMERIC(12,2) DEFAULT 0
);

-- =========================================================
-- 9. FINAL INVOICE
-- =========================================================
CREATE TABLE final_invoices (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    transport_invoice_id    UUID REFERENCES transport_invoices(id),
    -- Header
    invoice_no              TEXT NOT NULL,
    invoice_date            DATE NOT NULL DEFAULT CURRENT_DATE,
    party_id                UUID NOT NULL REFERENCES parties(id),
    agent_id                UUID REFERENCES agents(id),
    transporter_id          UUID REFERENCES transporters(id),
    destination             TEXT,
    documents_by            TEXT DEFAULT 'Direct',
    price_list_id           UUID REFERENCES price_lists(id),
    price_type              TEXT DEFAULT 'Wholesale',
    order_by                TEXT,
    order_thro              TEXT DEFAULT 'DIRECT',
    party_order_no          TEXT,
    party_order_date        DATE,
    qty_type                TEXT DEFAULT 'Pieces',
    -- Mandatory LR fields
    lr_no                   TEXT,
    lr_date                 DATE,
    no_of_boxes             INTEGER DEFAULT 0,
    freight_charges         NUMERIC(12,2) DEFAULT 0,
    -- Footer Totals (inherited + tax breakup)
    no_of_items             INTEGER DEFAULT 0,
    total_pcs               INTEGER DEFAULT 0,
    total_boxes             NUMERIC(10,2) DEFAULT 0,
    total_amount            NUMERIC(12,2) DEFAULT 0,
    gross_amount            NUMERIC(12,2) DEFAULT 0,
    less_sd_percent         NUMERIC(5,2) DEFAULT 0,
    less_sd_amount          NUMERIC(12,2) DEFAULT 0,
    less_trade_percent      NUMERIC(5,2) DEFAULT 0,
    less_trade_amount       NUMERIC(12,2) DEFAULT 0,
    less_cash_percent       NUMERIC(5,2) DEFAULT 0,
    less_cash_amount        NUMERIC(12,2) DEFAULT 0,
    taxable_amount          NUMERIC(12,2) DEFAULT 0,
    tax_type                TEXT DEFAULT 'IGST',
    tax_per                 NUMERIC(5,2) DEFAULT 5,
    cgst_amount             NUMERIC(12,2) DEFAULT 0,
    sgst_amount             NUMERIC(12,2) DEFAULT 0,
    igst_amount             NUMERIC(12,2) DEFAULT 0,
    tcs_amount              NUMERIC(12,2) DEFAULT 0,
    round_off               NUMERIC(10,2) DEFAULT 0,
    net_amount              NUMERIC(12,2) DEFAULT 0
);

CREATE TABLE final_invoice_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    final_invoice_id    UUID NOT NULL REFERENCES final_invoices(id) ON DELETE CASCADE,
    item_id             UUID NOT NULL REFERENCES items(id),
    size_value          TEXT NOT NULL,
    rate                NUMERIC(10,2) DEFAULT 0,
    qty_pieces          INTEGER DEFAULT 0,
    qty_boxes           NUMERIC(10,2) DEFAULT 0,
    amount              NUMERIC(12,2) DEFAULT 0
);

-- =========================================================
-- 10. FINANCIALS
-- =========================================================
CREATE TABLE receipt_vouchers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    voucher_no      TEXT,
    voucher_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    party_id        UUID REFERENCES parties(id),
    agent_id        UUID REFERENCES agents(id),
    amount          NUMERIC(12,2) DEFAULT 0,
    mode            TEXT,  -- Cash / Bank / Cheque
    narration       TEXT
);

CREATE TABLE payment_vouchers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    voucher_no      TEXT,
    voucher_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    party_id        UUID REFERENCES parties(id),
    agent_id        UUID REFERENCES agents(id),
    expense_id      UUID REFERENCES expense_ledgers(id),
    amount          NUMERIC(12,2) DEFAULT 0,
    mode            TEXT,
    narration       TEXT
);

CREATE TABLE ledger_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    entry_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    account_type    TEXT,   -- Party / Agent / Expense
    account_id      UUID NOT NULL,
    ref_type        TEXT,   -- Invoice / Receipt / Payment
    ref_id          TEXT,
    debit           NUMERIC(12,2) DEFAULT 0,
    credit          NUMERIC(12,2) DEFAULT 0,
    narration       TEXT
);

-- =========================================================
-- 11. ROW LEVEL SECURITY (Automatic SaaS Isolation)
-- =========================================================
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE transporters ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE banks ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxes ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE expense_ledgers ENABLE ROW LEVEL SECURITY;
ALTER TABLE general_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_list_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE parties ENABLE ROW LEVEL SECURITY;
ALTER TABLE party_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE packing_slips ENABLE ROW LEVEL SECURITY;
ALTER TABLE packing_slip_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE transport_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE transport_invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE final_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE final_invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipt_vouchers ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_vouchers ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_entries ENABLE ROW LEVEL SECURITY;


-- Add Festival Discount to Parties
ALTER TABLE parties 
ADD COLUMN discount_festival NUMERIC(5,2) DEFAULT 0;

-- Expand Bank Details
ALTER TABLE banks 
ADD COLUMN account_no TEXT,
ADD COLUMN ifsc_code TEXT,
ADD COLUMN branch TEXT;


-- Companies: user owns their own row
CREATE POLICY "company_select" ON companies FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY "company_insert" ON companies FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid());
CREATE POLICY "company_update" ON companies FOR UPDATE TO authenticated USING (user_id = auth.uid());

-- Macro: Apply SaaS policy to every other table
DO $$ DECLARE tbl TEXT;
BEGIN FOR tbl IN SELECT unnest(ARRAY[
    'transporters','agents','banks','taxes','staff','expense_ledgers','general_items',
    'items','price_lists','price_list_items',
    'parties','party_contacts',
    'orders','order_items',
    'packing_slips','packing_slip_items',
    'transport_invoices','transport_invoice_items',
    'final_invoices','final_invoice_items',
    'receipt_vouchers','payment_vouchers','ledger_entries'
]) LOOP
    EXECUTE format('
        CREATE POLICY "saas_all_%s" ON %I
        FOR ALL TO authenticated
        USING (company_id = get_user_company_id())
        WITH CHECK (company_id = get_user_company_id());
    ', tbl, tbl);
END LOOP; END $$;

-- =========================================================
-- 12. TEMPLATE SEED DATA (REPLICABLE FOR TESTING)
-- =========================================================
-- To replicate the system with test data, replace 'YOUR_COMPANY_ID_HERE' 
-- with your actual company UUID and run these commands.

DO $$
DECLARE
    v_comp_id UUID := 'd3cfc1bc-e57f-4d38-b5eb-a17a7fd45d7f'; -- Use your testing ID
    v_user_id UUID := (SELECT id FROM auth.users LIMIT 1); 
    v_agent_id UUID;
    v_trans_id UUID;
    v_tax_id UUID;
    v_item1_id UUID;
    v_plist_id UUID;
BEGIN
    -- Ensure Company exists
    IF NOT EXISTS (SELECT 1 FROM companies WHERE id = v_comp_id) THEN
        INSERT INTO companies (id, user_id, name, company_code)
        VALUES (v_comp_id, v_user_id, 'Mouliraj Garments', 'MRL001') ON CONFLICT DO NOTHING;
    END IF;

    -- Agent
    INSERT INTO agents (company_id, name, commission_percent, bank_name, bank_account, bank_ifsc)
    VALUES (v_comp_id, 'Krishna Agency', 5.0, 'HDFC Bank', '50100123456789', 'HDFC0001234')
    RETURNING id INTO v_agent_id;

    -- Transporter
    INSERT INTO transporters (company_id, name)
    VALUES (v_comp_id, 'VRL Logistics')
    RETURNING id INTO v_trans_id;

    -- Item
    INSERT INTO items (company_id, item_code, item_name, brand_name, sizes, pcs_per_inner_box, boxes_per_outer_box)
    VALUES (v_comp_id, 'TS-101', 'Cotton Round Neck T-Shirt', 'Mouliraj', ARRAY['S', 'M', 'L', 'XL'], 12, 10)
    RETURNING id INTO v_item1_id;

    -- Price List
    INSERT INTO price_lists (company_id, list_name, price_type)
    VALUES (v_comp_id, 'Standard Summer 2024', 'Wholesale')
    RETURNING id INTO v_plist_id;

    -- Size-wise rates
    INSERT INTO price_list_items (company_id, price_list_id, item_id, size_value, wholesale_rate, mrp_rate)
    SELECT v_comp_id, v_plist_id, v_item1_id, unnest(ARRAY['S', 'M', 'L', 'XL']), 150, 250;

    -- Party
    INSERT INTO parties (company_id, name, mobile, agent_id, transporter_id, price_list_id, price_type)
    VALUES (v_comp_id, 'Global Traders Chennai', '9876543210', v_agent_id, v_trans_id, v_plist_id, 'Wholesale');

END $$;
