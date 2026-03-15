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

1. In your Supabase dashboard, go to **SQL Editor**
2. Click **New query**
3. Open the file `supabase/schema.sql` from this repo and paste the entire contents into the editor
4. Click **Run** (green button)
5. You should see: `Success. No rows returned`

This creates 7 tables: `market_data`, `yield_curve`, `news_items`, `client_ideas`, `mufg_research`, `user_sources`, `app_meta` — all with Row Level Security enabled (public read-only, service role write).

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

### Step 7 — Configure the Dashboard

On first visit to your GitHub Pages URL, a **Setup** modal will appear. Enter:

- **Supabase URL** — your project URL
- **Supabase Anon Key** — the `anon` / public key (not the service key)
- **GitHub Repo** — format: `YOUR_USERNAME/indonesia-morning-brief`
- **GitHub PAT** — a Personal Access Token with `workflow` scope (needed for the "Refresh" button)

**To create a GitHub PAT:**
1. Go to GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Click **Generate new token (classic)**
3. Give it a name, set expiry (e.g. 90 days), check the **`workflow`** scope
4. Copy the token and paste it into the dashboard setup

These values are saved in your browser's `localStorage` — they never leave your browser.

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
    └── schema.sql                 # Database schema + RLS policies
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

- The **anon key** in the browser is read-only by design (Row Level Security policies)
- The **service role key** is only in GitHub Secrets, never in the browser or committed to the repo
- GitHub PAT is stored in browser `localStorage` only — it never goes to any server
- No user data is collected; the dashboard is purely a read display of your own Supabase data

---

## Data Attribution

Market data sourced from Yahoo Finance public API and FRED (Federal Reserve Bank of St. Louis). News from public RSS feeds. MUFG Research from mufgresearch.com. All data is for internal reference only.

---

*Built for MUFG Indonesia coverage — Energy, Commodities & FX*
