# MUFG Indonesia Morning Brief Dashboard

A GitHub Pages-hosted daily morning brief dashboard for MUFG Indonesia coverage — tracking commodities, FX, equities, yield curves, Indonesia macro, client ideas, and MUFG research updates.

---

## What This Does

- **Live market data** — Brent, coal, CPO, LNG, gold, silver, USD/IDR, AUD/IDR, CNY/IDR, SGD/IDR, IDX Composite, S&P 500, Nikkei, STI, and more
- **US Treasury yield curve** — 1M to 30Y from FRED for hedging context
- **Indonesia focus panel** — IDR live gauge, BI rate, sovereign ratings, MSCI inclusion status
- **Tabbed news feed** — Markets, Energy, Indonesia, Global — with keyword search and custom source entry
- **Client ideas** — Priority-ranked (CRITICAL / HIGH / MEDIUM / LOW) talking points auto-generated from market moves and news
- **MUFG Research tab** — Tom Joyce macro updates, article links, manual notes area
- **Sources management** — Add / toggle / remove custom RSS feeds directly in the dashboard

Data is fetched by a **GitHub Actions** job at **6:00 AM Jakarta time (WIB)** daily and stored in **Supabase**. The dashboard reads from Supabase via the public anon key (read-only). You can also trigger a manual refresh from the dashboard using a GitHub Personal Access Token.

---

## Prerequisites

- A free [Supabase](https://supabase.com) account
- A GitHub account
- A [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) (free, instant approval)

---

## Step-by-Step Setup

### Step 1 — Create a Supabase Project

1. Go to [https://supabase.com](https://supabase.com) and sign in
2. Click **New project**, choose a name (e.g. `indonesia-morning-brief`), set a database password, choose a region close to you (Singapore recommended)
3. Wait ~2 minutes for the project to provision
4. Go to **Settings → API** and note down:
   - **Project URL** — looks like `https://xxxxxxxxxxxx.supabase.co`
   - **`anon` / public key** — starts with `eyJ...` (this goes in the browser dashboard)
   - **`service_role` key** — starts with `eyJ...` (this goes in GitHub Secrets — keep it private!)

### Step 2 — Run the Database Schema

In your Supabase dashboard, go to **SQL Editor** → **New query**, and run each of the following files **in this order**. Each should return `Success. No rows returned`.

1. `supabase/schema.sql` — creates the 7 base tables (`market_data`, `yield_curve`, `news_items`, `client_ideas`, `mufg_research`, `user_sources`, `app_meta`) with Row Level Security.
2. `supabase/add_corruption_column.sql` — adds `is_corruption` to `news_items`.
3. `supabase/add_dedup_constraints.sql` — adds unique constraints so `ON CONFLICT` upserts work.
4. `supabase/add_flagged_articles.sql` — creates the `flagged_articles` table for the Risk Signals feature.
5. `supabase/tighten_rls.sql` — **security-critical**. Replaces the permissive `FOR ALL` policies on `user_sources` and `flagged_articles` with validated INSERT/UPDATE/DELETE policies (HTTPS-only URLs, MD5-12 id format, risk-level whitelist, length caps). Skip this file and your dashboard is exploitable by anyone who finds the public anon key.

After all five are applied, the database is in the hardened state. If you are upgrading an existing deployment, running the files again is safe — they all use `IF NOT EXISTS` / `DROP ... IF EXISTS` guards.

### Step 3 — Fork or Push to GitHub

**Option A — Fork from a template (if shared):**
Click **Fork** on the GitHub repo page.

**Option B — Push your own copy:**
```bash
git init
git add .
git commit -m "Initial commit: MUFG Indonesia Morning Brief"
git remote add origin https://github.com/YOUR_USERNAME/indonesia-morning-brief.git
git push -u origin main
```

### Step 4 — Add GitHub Secrets

These secrets are used by the GitHub Actions job to write data to Supabase.

1. Go to your GitHub repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret** and add the following two secrets:

| Secret Name | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase Project URL (e.g. `https://xxxx.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | Your Supabase `service_role` key |

> ⚠️ **Never commit the service role key to the repo.** It grants full database write access. GitHub Secrets keeps it encrypted.

### Step 5 — Enable GitHub Pages

1. Go to your GitHub repo → **Settings → Pages**
2. Under **Source**, select **Deploy from a branch**
3. Branch: `main`, Folder: `/ (root)`
4. Click **Save**
5. After ~1 minute, your dashboard will be live at:
   ```
   https://YOUR_USERNAME.github.io/indonesia-morning-brief/
   ```

### Step 6 — Run the First Data Fetch

The scheduled job runs at 6:00 AM WIB (23:00 UTC) daily. To fetch data immediately:

1. Go to your GitHub repo → **Actions** tab
2. Click **Update Morning Brief Data** in the left sidebar
3. Click **Run workflow** → **Run workflow** (green button)
4. Wait ~30–60 seconds for the job to complete
5. Refresh your dashboard — data should now appear

### Step 7 — Configure the Dashboard (admin only)

Only admins who want to manually trigger refreshes need this step. Public viewers do not — the site credentials are embedded in the page and refresh runs on cron regardless.

On first admin visit to your GitHub Pages URL, open the Admin Settings gear. Enter:

- **Supabase URL** — optional override; leave blank to use the site default
- **Supabase Anon Key** — optional override; leave blank to use the site default
- **GitHub Repo** — format: `YOUR_USERNAME/indonesia-morning-brief`
- **GitHub PAT (fine-grained)** — see instructions below

**Create the GitHub PAT as a fine-grained token with the minimum scope:**
1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens** (not the classic tab).
2. Click **Generate new token**.
3. Under **Repository access**, choose **Only select repositories** and pick this repo.
4. Under **Repository permissions**, set **Actions** to **Read and write**. Leave everything else at `No access`.
5. Set **Expiration** to **30 days** and put a calendar reminder to rotate it.
6. Generate, copy the token, paste it into the dashboard's Admin Settings.

**Why fine-grained, not classic:** The PAT sits in the browser's `localStorage` so the Refresh button can call `api.github.com`. If the browser ever executes hostile JavaScript — via a browser-extension compromise, a future XSS, or a compromised dependency — `localStorage` is readable and the token is exfiltrated. A classic PAT with `repo` or `workflow` scope grants broad, cross-repo write access; a fine-grained PAT scoped to `Actions: Read and write` on this one repo limits the blast radius to "attacker can dispatch this one workflow." Rotate the token every 30 days so a leaked token stops working quickly.

**If you do not need manual refresh at all:** skip this entire step. The cron schedule in `.github/workflows/update.yml` already runs six times a day, and the dashboard works fine without the PAT — the Refresh button just stays hidden.

---

## Project Structure

```
indonesia-morning-brief/
├── index.html                     # Main dashboard (all 7 tabs)
├── fetch_data.py                  # Python data fetcher (runs in GitHub Actions)
├── requirements.txt               # Python dependencies
├── .nojekyll                      # Tells GitHub Pages to skip Jekyll processing
├── .github/
│   └── workflows/
│       └── update.yml             # GitHub Actions: schedule + manual dispatch
└── supabase/
    ├── schema.sql                 # Base tables + RLS (run first)
    ├── add_corruption_column.sql  # Adds is_corruption to news_items
    ├── add_dedup_constraints.sql  # Unique constraints for upserts
    ├── add_flagged_articles.sql   # Risk Signals table
    └── tighten_rls.sql            # Hardened RLS — REQUIRED before exposing dashboard
```

---

## Dashboard Tabs

| Tab | Contents |
|---|---|
| **Overview** | KPI movers, top headlines, priority client ideas, sector snapshot |
| **Markets** | Full commodity / FX / equity price tables + US yield curve chart |
| **Indonesia** | IDR gauge, BI rate, ratings, MSCI status, Indonesia-tagged news |
| **News** | Full news feed with category filters (Markets / Energy / Indonesia / Global) + search |
| **Client Ideas** | Priority-ranked discussion topics + sector impact panel + RM segment notes |
| **MUFG Research** | Tom Joyce macro context, recent MUFG articles, manual notes area |
| **Sources** | Manage custom RSS feeds, view default sources, edit connection settings |

---

## Customising Data Sources

### Default RSS Feeds (in `fetch_data.py`)

The script fetches from 10 sources by default:
- Reuters Business, Reuters Energy, Reuters Indonesia
- Bloomberg Markets, Bloomberg Energy
- Financial Times
- Antara News, CNBC Indonesia
- Jakarta Post
- EIA (US Energy Information Administration)

### Adding Custom Sources

In the dashboard's **Sources tab**, enter any RSS feed URL and click **Add Source**. It will be saved to the Supabase `user_sources` table and picked up by the next GitHub Actions run.

### Tracked Market Symbols

| Category | Symbols |
|---|---|
| **Energy** | Brent crude, WTI, natural gas, thermal coal (Newcastle), LNG Japan-Korea |
| **Agricultural/Soft** | CPO (crude palm oil), rubber, cocoa, wheat |
| **Metals** | Gold, silver, copper, nickel |
| **FX** | USD/IDR, AUD/IDR, CNY/IDR, SGD/IDR, DXY, EUR/USD |
| **Equities** | IDX Composite, S&P 500, Nasdaq, Nikkei 225, STI, FTSE 100 |
| **Rates (spot)** | US 10Y Treasury yield, Indonesia 10Y government bond yield |

---

## Client Ideas Logic

Ideas are auto-generated by rules in `fetch_data.py` based on:

- **Brent ≥ +1.5%** → CRITICAL: Upstream energy cost alert for energy-intensive sectors
- **Brent ≤ −1.5%** → HIGH: Downstream/consumer sector opportunity
- **IDR ≥ 16,500** → HIGH: IDR weakness — hedging alert for corporates with USD exposure
- **IDR weakens ≥ +1.0% in 1 day** → CRITICAL: IDR sharp move — urgent RM discussion
- **Natural gas ≥ +2%** → HIGH: Gas/LNG pricing alert for utilities and fertiliser clients
- **CPO ≥ +2%** → MEDIUM: Palm oil rally — plantation and trading client opportunity
- **JKSE ≥ +1% or ≤ −1%** → MEDIUM: IDX equity market move — equity-linked product discussion
- **S&P 500 ≤ −1.5%** → HIGH: US risk-off — discuss capital flows and hedging
- **Indonesia news count ≥ 5** → LOW: High Indonesia headline volume — good RM contact day

---

## Scheduled Job Details

- **Cron**: `0 23 * * *` UTC = **6:00 AM Jakarta (WIB)**
- **Manual trigger**: Available from the dashboard (requires GitHub PAT with `workflow` scope) or from the GitHub Actions tab
- **Timeout**: 10 minutes
- **Data written**: ~24 market prices, 8 yield curve tenors, up to 60 news articles, 5–7 client ideas, MUFG research articles, app metadata

---

## Troubleshooting

**Dashboard shows "Connect your data sources" / no data:**
- Ensure you've run the GitHub Actions job at least once
- Check your Supabase URL and anon key are correct in the Setup modal (Sources tab → Settings)

**GitHub Actions job fails:**
- Go to Actions tab → click the failed run → read the error log
- Most common cause: `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` secret is missing or incorrect

**"Refresh" button does nothing:**
- Ensure your GitHub PAT has the `workflow` scope
- Check that the GitHub repo name in settings matches exactly: `username/repo-name`

**Some market prices show as N/A:**
- Yahoo Finance occasionally rate-limits; the next scheduled run should recover
- FRED yields are pulled from public CSV endpoints — no API key needed

**MUFG Research articles not updating:**
- mufgresearch.com may be geo-restricted; the script falls back to a curated list of known articles
- Use the Notes area in the MUFG Research tab to paste Tom Joyce's latest LinkedIn updates manually

---

## Security Notes

- The **anon key** is public by design and embedded in the page. Read access to every table is unrestricted. Two tables — `user_sources` and `flagged_articles` — also accept anon INSERT/UPDATE/DELETE, constrained by the policies in `supabase/tighten_rls.sql` (HTTPS-only URLs, MD5-12 id format, risk-level whitelist, length caps). **Do not expose the dashboard publicly without running `tighten_rls.sql` first.**
- The **service role key** is only in GitHub Secrets — never in the browser, never committed to the repo. It bypasses RLS and is what the scheduled fetcher uses to write `news_items`, `market_data`, etc.
- The **GitHub PAT** used for the in-browser Refresh button is stored in the browser's `localStorage` and sent only to `api.github.com`. Because anything stored in `localStorage` is reachable by any JavaScript that runs on the page, an XSS on the dashboard would leak this token and grant repo/workflow access to the attacker. Give the PAT the minimum scope possible (a fine-grained PAT with `actions: write` on this one repo is sufficient), rotate it regularly, and do not give the PAT to users who only need to view the dashboard.
- All `flagged_articles` and `user_sources` content is rendered through HTML-escaping helpers (`esc()` / `safeUrl()` / `safeId()`) and the page ships a restrictive `Content-Security-Policy` meta tag, so untrusted data from those tables cannot inject script or exfiltrate via arbitrary origins even if someone writes malicious input.
- No user data is collected. The dashboard is a read display of your own Supabase data plus whatever items you flag.

---

## Data Attribution

Market data sourced from Yahoo Finance public API and FRED (Federal Reserve Bank of St. Louis). News from public RSS feeds. MUFG Research from mufgresearch.com. All data is for internal reference only.

---

*Built for MUFG Indonesia coverage — Energy, Commodities & FX*
