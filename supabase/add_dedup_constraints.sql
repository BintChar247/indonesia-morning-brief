-- ─── Deduplication constraints ───────────────────────────────────────────────
-- Required for upsert (ON CONFLICT) to work in fetch_data.py
-- Run once in Supabase SQL Editor:
--   https://supabase.com/dashboard/project/foueycrzskbdjchpgumx/sql/new

-- Step 1: Remove duplicate news_items (keep highest id per unique id value)
DELETE FROM news_items
WHERE ctid NOT IN (
  SELECT MAX(ctid) FROM news_items GROUP BY id
);

-- Step 2: Remove duplicate mufg_research rows (keep highest db row per title)
DELETE FROM mufg_research
WHERE ctid NOT IN (
  SELECT MAX(ctid) FROM mufg_research GROUP BY title
);

-- Step 3: Add unique constraints (safe now that duplicates are gone)
ALTER TABLE news_items
  ADD CONSTRAINT news_items_id_unique UNIQUE (id);

ALTER TABLE mufg_research
  ADD CONSTRAINT mufg_research_title_unique UNIQUE (title);
