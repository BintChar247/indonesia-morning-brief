-- ============================================================
-- MUFG Indonesia Morning Brief — Supabase Schema
-- Run this entire script once in Supabase SQL Editor
-- ============================================================

-- 1. Market Data (latest prices — upserted on each run)
CREATE TABLE IF NOT EXISTS market_data (
  symbol      TEXT PRIMARY KEY,
  name        TEXT,
  unit        TEXT,
  category    TEXT,   -- 'energy' | 'fx' | 'equities' | 'rates_spot' | 'agricultural' | 'metals'
  price       NUMERIC,
  change      NUMERIC,
  change_pct  NUMERIC,
  prev_close  NUMERIC,
  currency    TEXT,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 2. US Treasury Yield Curve
CREATE TABLE IF NOT EXISTS yield_curve (
  id          SERIAL PRIMARY KEY,
  tenor       TEXT,       -- '1M','3M','6M','1Y','2Y','5Y','10Y','30Y'
  yield_pct   NUMERIC,
  curve_type  TEXT DEFAULT 'US_TREASURY',
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 3. News Items (replaced each run, last 60 articles)
CREATE TABLE IF NOT EXISTS news_items (
  id           TEXT PRIMARY KEY,   -- MD5 hash of title
  title        TEXT,
  url          TEXT,
  source       TEXT,
  source_cat   TEXT,               -- 'markets' | 'energy' | 'indonesia' | 'global'
  published_raw TEXT,
  summary      TEXT,
  tags         TEXT[],             -- ['indonesia','energy','corruption','fx_rates','commodities','macro','global']
  is_indonesia  BOOLEAN DEFAULT FALSE,
  is_corruption BOOLEAN DEFAULT FALSE,
  is_energy     BOOLEAN DEFAULT FALSE,
  is_fx         BOOLEAN DEFAULT FALSE,
  is_macro      BOOLEAN DEFAULT FALSE,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Client Ideas (auto-generated, replaced each run)
CREATE TABLE IF NOT EXISTS client_ideas (
  id        SERIAL PRIMARY KEY,
  priority  TEXT,    -- 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  icon      TEXT,
  sector    TEXT,
  clients   TEXT,
  trigger   TEXT,
  topic     TEXT,
  products  TEXT,
  generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. MUFG Research Articles (scraped from mufgresearch.com, replaced each run)
CREATE TABLE IF NOT EXISTS mufg_research (
  id        SERIAL PRIMARY KEY,
  title     TEXT,
  url       TEXT UNIQUE,
  date_str  TEXT,
  author    TEXT,
  category  TEXT,    -- 'FX' | 'Macro' | 'Indonesia' | 'RATES'
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. User-managed custom RSS sources (NOT overwritten by fetch script)
CREATE TABLE IF NOT EXISTS user_sources (
  id        SERIAL PRIMARY KEY,
  name      TEXT NOT NULL,
  url       TEXT NOT NULL UNIQUE,
  category  TEXT DEFAULT 'custom',
  enabled   BOOLEAN DEFAULT TRUE,
  notes     TEXT,
  added_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 7. App Metadata (key-value store for last update time, status, etc.)
CREATE TABLE IF NOT EXISTS app_meta (
  key        TEXT PRIMARY KEY,
  value      TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed initial meta values
INSERT INTO app_meta (key, value) VALUES
  ('last_updated_display', 'Not yet fetched'),
  ('last_updated_at',      NULL),
  ('fetch_status',         'pending'),
  ('news_count',           '0'),
  ('ideas_count',          '0'),
  ('fetch_ts',             '0')
ON CONFLICT (key) DO NOTHING;

-- ─── Row Level Security ──────────────────────────────────────────────────────
-- Enable RLS on all tables (anon key = read-only for dashboard)

ALTER TABLE market_data   ENABLE ROW LEVEL SECURITY;
ALTER TABLE yield_curve   ENABLE ROW LEVEL SECURITY;
ALTER TABLE news_items    ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_ideas  ENABLE ROW LEVEL SECURITY;
ALTER TABLE mufg_research ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sources  ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_meta      ENABLE ROW LEVEL SECURITY;

-- Public read-only (anon key can SELECT, not INSERT/UPDATE/DELETE)
CREATE POLICY "public read market_data"   ON market_data   FOR SELECT USING (true);
CREATE POLICY "public read yield_curve"   ON yield_curve   FOR SELECT USING (true);
CREATE POLICY "public read news_items"    ON news_items    FOR SELECT USING (true);
CREATE POLICY "public read client_ideas"  ON client_ideas  FOR SELECT USING (true);
CREATE POLICY "public read mufg_research" ON mufg_research FOR SELECT USING (true);
CREATE POLICY "public read user_sources"  ON user_sources  FOR SELECT USING (true);
CREATE POLICY "public read app_meta"      ON app_meta      FOR SELECT USING (true);

-- Allow anon key to manage user_sources (add/toggle/delete custom RSS feeds)
CREATE POLICY "anon manage user_sources" ON user_sources
  FOR ALL USING (true) WITH CHECK (true);

-- ─── Indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_market_category ON market_data (category);
CREATE INDEX IF NOT EXISTS idx_news_indonesia   ON news_items  (is_indonesia);
CREATE INDEX IF NOT EXISTS idx_news_energy      ON news_items  (is_energy);
CREATE INDEX IF NOT EXISTS idx_news_tags        ON news_items  USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_ideas_priority   ON client_ideas(priority);
CREATE INDEX IF NOT EXISTS idx_mufg_category    ON mufg_research(category);
