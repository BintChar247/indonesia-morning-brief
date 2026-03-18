-- ============================================================
-- MUFG Indonesia Morning Brief — Add is_corruption column
-- Run this in Supabase SQL Editor BEFORE pushing the updated
-- fetch_data.py (which now writes is_corruption on each row).
-- ============================================================

ALTER TABLE news_items
  ADD COLUMN IF NOT EXISTS is_corruption BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_news_corruption
  ON news_items (is_corruption);
