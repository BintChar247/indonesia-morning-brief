-- ── Flagged Articles table ───────────────────────────────────────────────────
-- Run this in your Supabase SQL Editor to enable the Risk Signals / flagging feature

CREATE TABLE IF NOT EXISTS flagged_articles (
    id               text PRIMARY KEY,          -- matches news_items.id (MD5 hash)
    title            text NOT NULL,
    url              text,
    source           text,
    source_cat       text,
    summary          text,
    tags             text[]   DEFAULT '{}',
    is_indonesia     boolean  DEFAULT false,
    is_energy        boolean  DEFAULT false,
    flagged_at       timestamptz DEFAULT now(),
    risk_level       text     DEFAULT 'MEDIUM', -- CRITICAL / HIGH / MEDIUM / LOW
    risk_headline    text,
    client_opportunities jsonb DEFAULT '[]',    -- array of {segment, idea, urgency}
    sector_impacts       jsonb DEFAULT '[]',    -- array of {sector, impact, detail}
    last_computed    timestamptz
);

ALTER TABLE flagged_articles ENABLE ROW LEVEL SECURITY;

-- Public can read (dashboard browser)
CREATE POLICY "public read flagged_articles"  ON flagged_articles FOR SELECT USING (true);
-- Anon key can insert/update/delete (browser flagging actions)
CREATE POLICY "anon manage flagged_articles"  ON flagged_articles FOR ALL USING (true) WITH CHECK (true);

-- Index for fast queries
CREATE INDEX IF NOT EXISTS idx_flagged_risk_level ON flagged_articles(risk_level);
CREATE INDEX IF NOT EXISTS idx_flagged_at         ON flagged_articles(flagged_at DESC);
