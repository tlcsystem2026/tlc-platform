CREATE TABLE IF NOT EXISTS request_header (
    id SERIAL PRIMARY KEY,
    request_no TEXT,
    request_date DATE,
    customer_name TEXT,
    total_amount NUMERIC(14,2),
    source_file TEXT,
    source_type TEXT,
    raw_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_line (
    id SERIAL PRIMARY KEY,
    request_id INTEGER REFERENCES request_header(id) ON DELETE CASCADE,
    line_no INTEGER,
    product_code TEXT,
    product_name TEXT,
    quantity NUMERIC(14,2),
    unit_price NUMERIC(14,2),
    amount NUMERIC(14,2),
    tax_rate NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS compare_result (
    id SERIAL PRIMARY KEY,
    request_no TEXT,
    scope TEXT,
    field_name TEXT,
    pdf_value TEXT,
    excel_value TEXT,
    severity TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_request_header_no ON request_header(request_no);
CREATE INDEX IF NOT EXISTS idx_compare_result_no ON compare_result(request_no);
