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

CREATE TABLE IF NOT EXISTS marketplace_listings (
    id TEXT PRIMARY KEY,
    listing_id TEXT UNIQUE,
    item_id TEXT,
    title TEXT NOT NULL,
    sku TEXT,
    quantity INTEGER DEFAULT 0,
    price REAL DEFAULT 0,
    status TEXT DEFAULT 'Active',
    thumbnail_path TEXT,
    image_url TEXT,
    marketplace TEXT DEFAULT 'eBay',
    url TEXT,
    last_synced TEXT,
    payload TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    listing_id TEXT UNIQUE,
    thumbnail_path TEXT,
    last_synced TEXT,
    card_id TEXT,
    finish_id INTEGER,
    title TEXT NOT NULL,
    sku TEXT,
    quantity INTEGER DEFAULT 0,
    price REAL DEFAULT 0,
    status TEXT DEFAULT 'Draft',
    marketplace TEXT DEFAULT 'eBay',
    url TEXT,
    payload TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(card_id) REFERENCES cards(id),
    FOREIGN KEY(finish_id) REFERENCES card_finishes(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    order_number TEXT UNIQUE,
    listing_id TEXT,
    card_id TEXT,
    finish_id INTEGER,
    buyer TEXT,
    quantity INTEGER DEFAULT 0,
    subtotal REAL DEFAULT 0,
    shipping REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    total REAL DEFAULT 0,
    status TEXT DEFAULT 'Open',
    purchased_at TEXT,
    payload TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(card_id) REFERENCES cards(id),
    FOREIGN KEY(finish_id) REFERENCES card_finishes(id),
    FOREIGN KEY(listing_id) REFERENCES listings(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'text',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_listings_listing_id ON listings(listing_id);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_orders_order_number ON orders(order_number);
CREATE INDEX IF NOT EXISTS idx_orders_listing_id ON orders(listing_id);
CREATE INDEX IF NOT EXISTS idx_settings_updated_at ON settings(updated_at);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_listing_id ON marketplace_listings(listing_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_status ON marketplace_listings(status);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_last_synced ON marketplace_listings(last_synced);
"""