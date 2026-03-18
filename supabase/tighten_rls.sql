-- ============================================================
-- MUFG Indonesia Morning Brief — Tightened RLS Policies
-- Run this in Supabase SQL Editor AFTER the initial schema.sql
--
-- Problem: The original "anon manage" policies on user_sources
-- and flagged_articles allow anyone who views the page source
-- (and finds the public anon key) to INSERT arbitrary rows —
-- creating SSRF risk via malicious RSS URLs and data injection
-- into the Risk Signals panel.
--
-- Fix: Replace FOR ALL with split INSERT/UPDATE/DELETE policies
-- that include WITH CHECK constraints validating input shape.
-- ============================================================

-- ── user_sources ────────────────────────────────────────────
-- Risk: anyone could insert a malicious RSS URL → fetch_data.py
-- fetches it on next GitHub Actions run (SSRF).
-- Fix: enforce https:// URLs only, cap field lengths.

DROP POLICY IF EXISTS "anon manage user_sources" ON user_sources;

CREATE POLICY "anon insert user_sources" ON user_sources
  FOR INSERT WITH CHECK (
    url  LIKE 'https://%'       -- https only, no internal IPs
    AND length(url)  < 500
    AND length(name) < 200
    AND (category IS NULL OR category IN ('custom','indonesia','energy','markets','global'))
  );

CREATE POLICY "anon update user_sources" ON user_sources
  FOR UPDATE
  USING (true)
  WITH CHECK (
    url  LIKE 'https://%'
    AND length(url)  < 500
    AND length(name) < 200
  );

CREATE POLICY "anon delete user_sources" ON user_sources
  FOR DELETE USING (true);


-- ── flagged_articles ─────────────────────────────────────────
-- Risk: anyone could inject arbitrary risk_headline / client_
-- opportunities JSON into the Risk Signals panel. With XSS
-- escaping now in the frontend this is lower severity, but
-- still worth validating inputs.
-- Fix: enforce MD5-12 id format, cap title length, https URLs.

DROP POLICY IF EXISTS "anon manage flagged_articles" ON flagged_articles;

CREATE POLICY "anon insert flagged_articles" ON flagged_articles
  FOR INSERT WITH CHECK (
    length(id)    = 12                           -- MD5 hex[:12]
    AND id        ~ '^[0-9a-f]{12}$'             -- hex chars only
    AND length(title) BETWEEN 1 AND 1000
    AND (url IS NULL OR url LIKE 'http%')
    AND risk_level IN ('CRITICAL','HIGH','MEDIUM','LOW')
  );

CREATE POLICY "anon update flagged_articles" ON flagged_articles
  FOR UPDATE
  USING (true)
  WITH CHECK (
    length(title) BETWEEN 1 AND 1000
    AND (url IS NULL OR url LIKE 'http%')
    AND risk_level IN ('CRITICAL','HIGH','MEDIUM','LOW')
  );

CREATE POLICY "anon delete flagged_articles" ON flagged_articles
  FOR DELETE USING (true);
