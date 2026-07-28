SCHEMA = """
CREATE TABLE IF NOT EXISTS sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT,
    release_date TEXT,
    printed_total INTEGER
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL,
    number TEXT,
    name TEXT,
    rarity TEXT,

    FOREIGN KEY(set_id) REFERENCES sets(id)
);

CREATE TABLE IF NOT EXISTS card_finishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    finish TEXT NOT NULL,
    image_path TEXT,
    github_url TEXT,

    UNIQUE(card_id, finish),

    FOREIGN KEY(card_id) REFERENCES cards(id)
);

CREATE TABLE IF NOT EXISTS inventory (
    card_id TEXT PRIMARY KEY,
    quantity INTEGER DEFAULT 0,
    cost_price REAL DEFAULT 0,
    sell_price REAL DEFAULT 0,

    FOREIGN KEY(card_id) REFERENCES cards(id)
);

CREATE TABLE IF NOT EXISTS ebay (
    card_id TEXT PRIMARY KEY,
    listing_id TEXT,
    listed INTEGER DEFAULT 0,
    last_sync TEXT,

    FOREIGN KEY(card_id) REFERENCES cards(id)
);

CREATE TABLE IF NOT EXISTS finish_workspace (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finish_id INTEGER NOT NULL UNIQUE,
    quantity INTEGER DEFAULT 0,
    cost_price REAL DEFAULT 0,
    sell_price REAL DEFAULT 0,
    market_price REAL DEFAULT 0,
    image_path TEXT,
    github_url TEXT,
    ebay_listing_id TEXT,
    ebay_status TEXT,
    queued_at TEXT,
    exported_at TEXT,
    listing_group TEXT,
    listing_type TEXT,
    export_batch TEXT,
    listing_title_override TEXT,
    ebay_error TEXT,
    is_image_verified INTEGER DEFAULT 0,
    is_ready_for_listing INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(finish_id) REFERENCES card_finishes(id)
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id TEXT PRIMARY KEY,
    order_number TEXT,
    sale_date TEXT,
    platform TEXT,
    buyer TEXT,
    card_id TEXT,
    finish_id INTEGER,
    quantity INTEGER DEFAULT 0,
    sale_price REAL DEFAULT 0,
    fees REAL DEFAULT 0,
    shipping_cost REAL DEFAULT 0,
    status TEXT DEFAULT 'Completed',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(card_id) REFERENCES cards(id),
    FOREIGN KEY(finish_id) REFERENCES card_finishes(id)
);

CREATE INDEX IF NOT EXISTS idx_cards_set_id ON cards(set_id);
CREATE INDEX IF NOT EXISTS idx_card_finishes_card_id ON card_finishes(card_id);
CREATE INDEX IF NOT EXISTS idx_finish_workspace_finish_id ON finish_workspace(finish_id);
CREATE INDEX IF NOT EXISTS idx_sales_card_id ON sales(card_id);
CREATE INDEX IF NOT EXISTS idx_sales_finish_id ON sales(finish_id);
CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date);
"""