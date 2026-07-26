DROP TABLE IF EXISTS daily_prices;
DROP TABLE IF EXISTS mandis;

CREATE TABLE mandis (
    mandi_id    TEXT PRIMARY KEY,
    mandi_name  TEXT NOT NULL,
    district    TEXT,
    state       TEXT NOT NULL
);

CREATE TABLE daily_prices (
    mandi_id    TEXT NOT NULL REFERENCES mandis(mandi_id),
    price_date  DATE NOT NULL,
    commodity   TEXT NOT NULL,
    arrivals    REAL,
    min_price   REAL,
    max_price   REAL,
    modal_price REAL
);

CREATE INDEX idx_prices_mandi_date ON daily_prices(mandi_id, price_date);
CREATE INDEX idx_prices_commodity  ON daily_prices(commodity);
