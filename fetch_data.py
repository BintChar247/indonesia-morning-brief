#!/usr/bin/env python3
"""
MUFG Indonesia Morning Brief — Data Fetcher
Runs daily at 6am WIB (23:00 UTC) via GitHub Actions.
Fetches: Yahoo Finance quotes, FRED yield curves, RSS news, generates client ideas,
         scrapes MUFG Research articles — then writes everything to Supabase.
"""

import json, os, re, time, hashlib, datetime, requests, feedparser
from typing import Dict, List, Optional
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

# ─── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")   # service-role key (write access)
WIB_OFFSET   = 7                                             # UTC+7

def now_wib() -> datetime.datetime:
    return datetime.datetime.utcnow() + datetime.timedelta(hours=WIB_OFFSET)

def sb_post(table: str, payload, method: str = "POST") -> dict:
    """Raw Supabase REST call — avoids supabase-py version conflicts."""
    url     = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }
    r = requests.request(method, url, headers=headers, json=payload, timeout=20)
    if r.status_code not in (200, 201, 204):
        print(f"  ⚠ Supabase {method} {table}: {r.status_code} {r.text[:200]}")
    return r

def sb_delete(table: str, filter_col: str, filter_val) -> None:
    url     = f"{SUPABASE_URL}/rest/v1/{table}?{filter_col}=not.is.null"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer":        "return=minimal",
    }
    requests.delete(url, headers=headers, timeout=15)

# ─── Yahoo Finance ────────────────────────────────────────────────────────────
YAHOO_SYMBOLS: Dict[str, Dict] = {
    # Commodities
    "BZ=F":     {"name": "Brent Crude",   "unit": "USD/bbl",    "category": "energy"},
    "CL=F":     {"name": "WTI Crude",     "unit": "USD/bbl",    "category": "energy"},
    "NG=F":     {"name": "Natural Gas",   "unit": "USD/MMBtu",  "category": "energy"},
    "GC=F":     {"name": "Gold",          "unit": "USD/oz",     "category": "metals"},
    "SI=F":     {"name": "Silver",        "unit": "USD/oz",     "category": "metals"},
    "HG=F":     {"name": "Copper",        "unit": "USD/lb",     "category": "metals"},
    "ZW=F":     {"name": "Wheat",         "unit": "USc/bu",     "category": "agricultural"},
    "ZS=F":     {"name": "Soybeans",      "unit": "USc/bu",     "category": "agricultural"},
    "FKPO.KLS": {"name": "CPO Palm Oil",  "unit": "MYR/tonne",  "category": "agricultural"},
    # FX
    "IDR=X":    {"name": "USD/IDR",       "unit": "Rp",         "category": "fx"},
    "SGD=X":    {"name": "USD/SGD",       "unit": "SGD",        "category": "fx"},
    "EURUSD=X": {"name": "EUR/USD",       "unit": "USD",        "category": "fx"},
    "JPY=X":    {"name": "USD/JPY",       "unit": "¥",          "category": "fx"},
    "CNY=X":    {"name": "USD/CNY",       "unit": "CNY",        "category": "fx"},
    "MYR=X":    {"name": "USD/MYR",       "unit": "MYR",        "category": "fx"},
    "DX-Y.NYB": {"name": "DXY Index",     "unit": "",           "category": "fx"},
    # Equities
    "^GSPC":    {"name": "S&P 500",       "unit": "",           "category": "equities"},
    "^IXIC":    {"name": "Nasdaq",        "unit": "",           "category": "equities"},
    "^DJI":     {"name": "Dow Jones",     "unit": "",           "category": "equities"},
    "^STI":     {"name": "SGX STI",       "unit": "",           "category": "equities"},
    "^JKSE":    {"name": "IDX Composite", "unit": "",           "category": "equities"},
    "^STOXX50E":{"name": "Euro Stoxx 50", "unit": "",           "category": "equities"},
    "^N225":    {"name": "Nikkei 225",    "unit": "",           "category": "equities"},
    "^HSI":     {"name": "Hang Seng",     "unit": "",           "category": "equities"},
    # Rates (spot)
    "^TNX":     {"name": "US 10Y Yield",  "unit": "%",          "category": "rates_spot"},
    "^FVX":     {"name": "US 5Y Yield",   "unit": "%",          "category": "rates_spot"},
    "^TYX":     {"name": "US 30Y Yield",  "unit": "%",          "category": "rates_spot"},
}

def fetch_yahoo_batch(symbols: List[str]) -> Dict:
    """Fetch quotes using yfinance (primary) with v7 API fallback."""
    results = {}

    # ── Primary: yfinance library ──────────────────────────────────────────
    if YFINANCE_AVAILABLE:
        try:
            tickers = yf.Tickers(" ".join(symbols))
            for sym in symbols:
                try:
                    info = tickers.tickers[sym].fast_info
                    prev = getattr(info, "previous_close", None) or getattr(info, "regularMarketPreviousClose", None)
                    price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
                    if price:
                        change = (price - prev) if prev else 0
                        change_pct = (change / prev * 100) if prev else 0
                        results[sym] = {
                            "symbol": sym,
                            "regularMarketPrice": price,
                            "regularMarketChange": change,
                            "regularMarketChangePercent": change_pct,
                            "regularMarketPreviousClose": prev,
                            "shortName": YAHOO_SYMBOLS.get(sym, {}).get("name", sym),
                        }
                except Exception:
                    pass
            if results:
                print(f"  ✓ yfinance: {len(results)}/{len(symbols)} symbols")
                # fill missing via v7 fallback below
                missing = [s for s in symbols if s not in results]
                if missing:
                    print(f"  → fallback for {len(missing)} missing symbols via v7 API")
                    v7 = _fetch_yahoo_v7(missing)
                    results.update(v7)
                return results
        except Exception as e:
            print(f"  ⚠ yfinance error: {e} — trying v7 API fallback")

    # ── Fallback: Yahoo Finance v7 REST API ────────────────────────────────
    return _fetch_yahoo_v7(symbols)

def _fetch_yahoo_v7(symbols: List[str]) -> Dict:
    """Direct Yahoo Finance v7 API call with rotating user agents."""
    import random
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    ]
    syms = ",".join(symbols)
    url  = (
        "https://query1.finance.yahoo.com/v8/finance/quote"
        f"?symbols={syms}"
        "&fields=regularMarketPrice,regularMarketChange,regularMarketChangePercent,"
        "regularMarketPreviousClose,shortName,currency,regularMarketTime"
    )
    headers = {
        "User-Agent":      random.choice(user_agents),
        "Accept":          "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://finance.yahoo.com/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        results = r.json().get("quoteResponse", {}).get("result", [])
        out = {q["symbol"]: q for q in results if q.get("regularMarketPrice")}
        print(f"  ✓ v8 API: {len(out)}/{len(symbols)} symbols")
        return out
    except Exception as e:
        print(f"  ⚠ Yahoo v8 API: {e}")
        # Try v7 as last resort
        try:
            url2 = url.replace("v8", "v7")
            r2 = requests.get(url2, headers=headers, timeout=30)
            r2.raise_for_status()
            results2 = r2.json().get("quoteResponse", {}).get("result", [])
            out2 = {q["symbol"]: q for q in results2 if q.get("regularMarketPrice")}
            print(f"  ✓ v7 API: {len(out2)}/{len(symbols)} symbols")
            return out2
        except Exception as e2:
            print(f"  ✗ All Yahoo Finance attempts failed: {e2}")
            return {}

# ─── FRED Yield Curve ─────────────────────────────────────────────────────────
FRED_SERIES = {
    "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
    "1Y": "DGS1",   "2Y": "DGS2",   "5Y": "DGS5",
    "10Y": "DGS10", "30Y": "DGS30",
}

def fetch_fred_yields() -> Dict[str, Optional[float]]:
    yields = {}
    for tenor, sid in FRED_SERIES.items():
        try:
            r     = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=12)
            lines = [l for l in r.text.strip().split("\n") if l and not l.startswith("DATE")]
            if lines:
                val = lines[-1].split(",")[1].strip()
                yields[tenor] = float(val) if val not in (".", "", "nan") else None
            else:
                yields[tenor] = None
        except Exception as e:
            print(f"  ⚠ FRED {tenor}: {e}")
            yields[tenor] = None
    return yields

# ─── News ─────────────────────────────────────────────────────────────────────
RSS_SOURCES = [
    {"name": "Yahoo Finance",       "url": "https://finance.yahoo.com/rss/topstories",                      "cat": "markets"},
    {"name": "CNBC Markets",        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",          "cat": "markets"},
    {"name": "OilPrice.com",        "url": "https://oilprice.com/rss/main",                                  "cat": "energy"},
    {"name": "Jakarta Post",        "url": "https://www.thejakartapost.com/feed",                            "cat": "indonesia"},
    {"name": "Investing.com",       "url": "https://www.investing.com/rss/news.rss",                         "cat": "markets"},
    {"name": "MarketWatch",         "url": "https://www.marketwatch.com/rss/realtimeheadlines",              "cat": "markets"},
    {"name": "The Guardian Biz",    "url": "https://www.theguardian.com/business/rss",                       "cat": "global"},
    {"name": "Reuters Commodities", "url": "https://finance.yahoo.com/rss/industry?ind=Energy&lang=en-US",  "cat": "energy"},
    {"name": "Bisnis Indonesia",    "url": "https://bisnis.com/feed",                                        "cat": "indonesia"},
    {"name": "Kontan",              "url": "https://rss.kontan.co.id/",                                      "cat": "indonesia"},
]

ID_KW   = {"indonesia","indonesian","idr","rupiah","pertamina","pln","bri","mandiri","bca","danamon","jakarta","prabowo","bank indonesia","jkse","idx","msci","bulog","pgn","bi rate","bapanas"}
EN_KW   = {"oil","crude","brent","wti","lng","lpg","natural gas","opec","hormuz","energy","petroleum","coal","barrel","refinery","gasoline"}
FX_KW   = {"dollar","usd","currency","fx","forex","exchange rate","federal reserve","interest rate","monetary","inflation","cpi","hawkish","dovish","yield","treasury"}
COM_KW  = {"nickel","palm oil","cpo","wheat","rice","gold","copper","tin","commodity","metals","agriculture","soybean"}
MAC_KW  = {"gdp","recession","stagflation","growth","sovereign","rating","moody","fitch","s&p","debt","fiscal","tariff","trade war","geopolit"}

def tag_article(title: str, summary: str = "") -> List[str]:
    text = (title + " " + summary).lower()
    tags = []
    if any(k in text for k in ID_KW):  tags.append("indonesia")
    if any(k in text for k in EN_KW):  tags.append("energy")
    if any(k in text for k in FX_KW):  tags.append("fx_rates")
    if any(k in text for k in COM_KW): tags.append("commodities")
    if any(k in text for k in MAC_KW): tags.append("macro")
    return tags if tags else ["global"]

def fetch_all_news() -> List[Dict]:
    items, seen = [], set()
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for e in feed.entries[:10]:
                title = (e.get("title") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                raw_sum = e.get("summary") or e.get("description") or ""
                summary = re.sub(r"<[^>]+>", "", raw_sum)[:300].strip()
                tags    = tag_article(title, summary)
                items.append({
                    "id":           hashlib.md5(title.encode()).hexdigest()[:12],
                    "title":        title,
                    "url":          e.get("link", ""),
                    "source":       src["name"],
                    "source_cat":   src["cat"],
                    "published_raw":e.get("published", ""),
                    "summary":      summary,
                    "tags":         tags,
                    "is_indonesia": "indonesia" in tags,
                    "is_energy":    "energy"    in tags,
                    "is_fx":        "fx_rates"  in tags,
                    "is_macro":     "macro"     in tags,
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠ RSS [{src['name']}]: {e}")
    return items

# ─── Client Ideas (rules-based) ───────────────────────────────────────────────
def generate_client_ideas(market_rows: List[Dict], news: List[Dict]) -> List[Dict]:
    # Build quick lookup by symbol
    q = {r["symbol"]: r for r in market_rows}
    ideas = []

    def pct(sym): return float(q.get(sym, {}).get("change_pct", 0) or 0)
    def price(sym): return float(q.get(sym, {}).get("price", 0) or 0)

    brent_p, brent_c = price("BZ=F"), pct("BZ=F")
    idr_p,   idr_c   = price("IDR=X"), pct("IDR=X")
    gas_c            = pct("NG=F")
    jkse_c           = pct("^JKSE")
    spx_c            = pct("^GSPC")
    cpo_c            = pct("FKPO.KLS")

    # Oil shock
    if abs(brent_c) >= 1.5:
        d = "SURGE" if brent_c > 0 else "DROP"
        ideas.append({
            "priority": "HIGH", "icon": "⚡", "sector": "Energy & Utilities",
            "clients":  "Pertamina, PLN, PGN, Bulog",
            "trigger":  f"Brent {'+' if brent_c>0 else ''}{brent_c:.1f}% → ${brent_p:.0f}/bbl ({d})",
            "topic":    (
                f"Crude oil {'surge demands urgent hedge review' if brent_c>0 else 'drop — review hedge structures at lower strikes'}. "
                f"Pertamina procurement cost {'rising sharply — consider cap/collar on forward crude purchases. MUFG sensitivity: +$10/bbl = +0.4pp CPI, −0.2% GDP trade balance.' if brent_c>0 else 'easing — window to restructure hedges, potentially buy low-cost caps.'}  "
                f"PLN LNG input costs {'rising — government subsidy transfer pressure' if brent_c>0 else 'easing'}. "
                f"ART energy clause: US import obligation at current Brent implies locked-in cost premium vs. spot alternatives. "
                f"Bulog CIF import cost review for rice/wheat."
            ),
            "products": "Commodity swap, Oil cap/collar, Import LC, Trade Finance, Price risk advisory",
        })

    # IDR pressure
    idr_alert = "CRITICAL" if idr_p >= 17000 else "HIGH" if idr_p >= 16700 else "MEDIUM"
    if idr_p >= 16500 or abs(idr_c) >= 0.3:
        ideas.append({
            "priority": idr_alert, "icon": "💱", "sector": "FX — All Segments",
            "clients":  "All USD-exposed clients (SOEs, MNCs, Conglomerates)",
            "trigger":  f"USD/IDR {'+' if idr_c>0 else ''}{idr_c:.2f}% → Rp {idr_p:,.0f}",
            "topic":    (
                f"{'🚨 IDR at/above MUFG red-line 17,000 — URGENT hedge review.' if idr_p>=17000 else 'IDR under pressure.'} "
                f"MUFG target: Rp 17,000 base / Rp 17,400 tail-risk. "
                f"Review USD debt service for all conglomerate clients (Adaro, Sinar Mas, Salim). "
                f"NDF/forward positioning for MNC dividend repatriation and import payments. "
                f"Cross-currency swap opportunities for PLN and Pertamina USD bond servicing. "
                f"BI: held 4.75% for 6 months — MUFG forecasts 2×25bp cuts in 2026 (pushed to Q2+)."
            ),
            "products": "FX Forward, NDF, Cross-Currency Swap, FX Option, Risk Reversal",
        })

    # Natural gas
    if abs(gas_c) >= 2:
        ideas.append({
            "priority": "HIGH", "icon": "🔥", "sector": "Petrochemicals & Agriculture",
            "clients":  "Pupuk Indonesia, Chemical MNCs, PLN gas fleet clients",
            "trigger":  f"Natural Gas {'+' if gas_c>0 else ''}{gas_c:.1f}%",
            "topic":    (
                f"Gas price {'surge' if gas_c>0 else 'drop'} — "
                f"{'Fertiliser (urea) production costs rising → Pupuk Indonesia margin pressure → potential passthrough to rice/corn farmers = food security risk. PLN gas-fired generation (23% of grid) cost rising. Chemical MNC LNG/naphtha feedstock review.' if gas_c>0 else 'Easing fertiliser input costs — window to review gas supply hedges at lower levels. LNG procurement timing discussion.'}"
            ),
            "products": "Gas price swap, LNG trade finance, Commodity hedge",
        })

    # CPO / Palm oil
    if abs(cpo_c) >= 2:
        ideas.append({
            "priority": "MEDIUM", "icon": "🌴", "sector": "Agricultural Commodities",
            "clients":  "Sinar Mas, Asian Agri, Wilmar, CPO exporters",
            "trigger":  f"CPO {'+' if cpo_c>0 else ''}{cpo_c:.1f}%",
            "topic":    (
                f"CPO {'rally' if cpo_c>0 else 'weakness'} — Indonesia's largest export (USD 20.2B in 2025). "
                f"{'Review export revenue hedges, discuss B40 biodiesel mandate impact on domestic CPO demand vs. export allocation.' if cpo_c>0 else 'Review hedge coverage for CPO exporters, discuss B40 mandate pricing implications.'}"
            ),
            "products": "Commodity hedge, Export finance, FX forward for USD export revenues",
        })

    # IDX equity market
    if abs(jkse_c) >= 1:
        ideas.append({
            "priority": "MEDIUM", "icon": "📈", "sector": "Financial Services (FIG)",
            "clients":  "Danamon, Top FIG clients, Conglomerate treasury teams",
            "trigger":  f"IDX Composite {'+' if jkse_c>=0 else ''}{jkse_c:.1f}%",
            "topic":    (
                f"{'Equity market recovery — potential capital markets window. Discuss bond/equity issuance timing with FIG and conglomerate clients.' if jkse_c>0 else 'Market under pressure — review MSCI May 2026 reclassification risk, portfolio collateral marks, NPL build-up in energy/manufacturing exposure.'} "
                f"BI rate path update. MSCI deadline: May 2026."
            ),
            "products": "DCM/ECM advisory, Capital markets, Equity-linked structured notes",
        })

    # US market risk-off
    if spx_c <= -1.5:
        ideas.append({
            "priority": "MEDIUM", "icon": "🌐", "sector": "MNCs & Global Corporates",
            "clients":  "MNC treasury heads, HQ-driven global clients",
            "trigger":  f"S&P 500 {spx_c:.1f}% — risk-off",
            "topic":    (
                f"US equity weakness triggering risk-off globally. Possible EM capital outflows — prepare for further IDR weakness beyond MUFG 17,000 target. "
                f"Discuss USD hedging windows, safe-haven asset rebalancing, and supply chain finance tightening implications for Indonesian subsidiaries."
            ),
            "products": "FX hedging, Risk advisory, Supply chain finance",
        })

    # Indonesia-specific headlines
    id_news = [n for n in news if n.get("is_indonesia")]
    if id_news:
        ideas.append({
            "priority": "MEDIUM", "icon": "🇮🇩", "sector": "Sovereign & Macro Monitoring",
            "clients":  "SOE CFOs, FIG senior management, Govt-linked entities",
            "trigger":  f"{len(id_news)} Indonesia headline(s) today",
            "topic":    (
                f"Share morning brief Indonesia highlights. Key monitoring: "
                f"Credit ratings (Moody's Baa2 Neg | Fitch BBB Neg | S&P Watch Neg). "
                f"MSCI EM→FM reclassification review: May 2026. "
                f"BI reserve adequacy. Budget deficit (IDR 54.6T vs 23.5T a year ago). "
                f"5Y CDS above 80bps. Government spending +25.7% YoY."
            ),
            "products": "Macro advisory, Liability management, Risk management",
        })

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(ideas, key=lambda x: order.get(x["priority"], 3))

# ─── MUFG Research ────────────────────────────────────────────────────────────
MUFG_FALLBACK = [
    {"title": "Asia FX Weekly: Asian currencies under pressure — oil & stagflation risks",
     "url": "https://www.mufgresearch.com/fx/asia-fx-weekly-13-march-2026/",
     "date_str": "13 Mar 2026", "author": "MUFG FX Research", "category": "FX"},
    {"title": "Asia FX Talk: Oil shock reignites inflation risks",
     "url": "https://www.mufgresearch.com/fx/asia-fx-talk-oil-shock-reignites-inflation-risks-13-march-2026/",
     "date_str": "13 Mar 2026", "author": "MUFG FX Research", "category": "FX"},
    {"title": "Indonesia: Rupiah faces pressure from oil and risk-off sentiment",
     "url": "https://www.mufgresearch.com/fx/indonesia-rupiah-faces-pressure-from-oil-and-risk-off-sentiment-3-march-2026/",
     "date_str": "3 Mar 2026",  "author": "MUFG FX Research", "category": "Indonesia"},
    {"title": "Asia FX Weekly: US-Israel war with Iran remains the focus",
     "url": "https://www.mufgresearch.com/fx/asia-fx-weekly-6-march-2026/",
     "date_str": "6 Mar 2026",  "author": "MUFG FX Research", "category": "FX"},
    {"title": "Indonesia: BI on hold amid persistent rupiah weakness",
     "url": "https://www.mufgresearch.com/fx/indonesia-bi-on-hold-amid-persistent-rupiah-weakness-20-february-2026/",
     "date_str": "20 Feb 2026", "author": "MUFG FX Research", "category": "Indonesia"},
    {"title": "US Inflation Update — March 10, 2026",
     "url": "https://www.mufgresearch.com/macro/us-inflation-update-march-10-2026/",
     "date_str": "10 Mar 2026", "author": "MUFG Macro Research", "category": "Macro"},
    {"title": "Capital Markets Strategy: Transformative Change",
     "url": "https://www.mufgresearch.com/macro/capital-markets-strategy-19-january-2026/",
     "date_str": "19 Jan 2026", "author": "Tom Joyce, MUFG", "category": "Macro"},
    {"title": "Monthly FX Outlook — March 2026",
     "url": "https://www.mufgresearch.com/fx/monthly-foreign-exchange-outlook-march-2026/",
     "date_str": "1 Mar 2026",  "author": "MUFG FX Research", "category": "FX"},
    {"title": "Macro2Markets: 2026 Outlook — Smooth Sailing Ahead?",
     "url": "https://www.mufgresearch.com/rates/us-macro-strategy-2026-outlook-19-december-2025/",
     "date_str": "19 Dec 2025", "author": "MUFG Rates Research", "category": "Macro"},
    {"title": "Asia FX Talk: A drop in the bucket, or a big splash?",
     "url": "https://www.mufgresearch.com/fx/asia-fx-talk-a-drop-in-the-bucket-or-a-big-splash-12-march-2026/",
     "date_str": "12 Mar 2026", "author": "MUFG FX Research", "category": "FX"},
]

def fetch_mufg_research() -> List[Dict]:
    from bs4 import BeautifulSoup
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}
    articles = []
    for section in ["fx", "macro", "rates"]:
        try:
            r = requests.get(f"https://www.mufgresearch.com/{section}/", headers=hdrs, timeout=12)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    text = a.get_text(strip=True)
                    if (f"/{section}/" in href and len(text) > 25
                            and any(y in href for y in ["2026", "2025"])
                            and href not in [x["url"] for x in articles]):
                        full_url = href if href.startswith("http") else f"https://www.mufgresearch.com{href}"
                        m = re.search(r"\d{1,2}-\w+-\d{4}|\d{4}", href)
                        articles.append({
                            "title":    text,
                            "url":      full_url,
                            "date_str": m.group(0).replace("-", " ") if m else "",
                            "author":   "MUFG Research",
                            "category": section.upper(),
                        })
        except Exception as e:
            print(f"  ⚠ MUFG scrape [{section}]: {e}")
    return articles[:15] if articles else MUFG_FALLBACK

# ─── Supabase Writers ─────────────────────────────────────────────────────────
def write_market_data(quotes: Dict) -> List[Dict]:
    rows = []
    for sym, meta in YAHOO_SYMBOLS.items():
        q = quotes.get(sym, {})
        if not q:
            continue
        rows.append({
            "symbol":     sym,
            "name":       meta["name"],
            "unit":       meta.get("unit", ""),
            "category":   meta["category"],
            "price":      round(float(q.get("regularMarketPrice") or 0), 4),
            "change":     round(float(q.get("regularMarketChange") or 0), 4),
            "change_pct": round(float(q.get("regularMarketChangePercent") or 0), 2),
            "prev_close": round(float(q.get("regularMarketPreviousClose") or 0), 4),
            "currency":   q.get("currency", "USD"),
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        })
    if rows:
        sb_post("market_data", rows)
        print(f"  ✓ market_data: {len(rows)} rows upserted")
    return rows

def write_yield_curve(yields: Dict) -> None:
    # Delete old, insert fresh
    sb_delete("yield_curve", "tenor", None)
    rows = [{"tenor": k, "yield_pct": v, "curve_type": "US_TREASURY",
             "updated_at": datetime.datetime.utcnow().isoformat() + "Z"}
            for k, v in yields.items() if v is not None]
    if rows:
        sb_post("yield_curve", rows)
        print(f"  ✓ yield_curve: {len(rows)} tenors")

def write_news(news: List[Dict]) -> None:
    sb_delete("news_items", "id", None)
    if news:
        sb_post("news_items", news[:60])
        print(f"  ✓ news_items: {len(news[:60])} articles")

def write_client_ideas(ideas: List[Dict]) -> None:
    sb_delete("client_ideas", "priority", None)
    if ideas:
        sb_post("client_ideas", ideas)
        print(f"  ✓ client_ideas: {len(ideas)} ideas")

def write_mufg_research(articles: List[Dict]) -> None:
    sb_delete("mufg_research", "title", None)
    if articles:
        sb_post("mufg_research", articles)
        print(f"  ✓ mufg_research: {len(articles)} articles")

def write_app_meta(status: str, news_count: int, ideas_count: int) -> None:
    now = now_wib()
    rows = [
        {"key": "last_updated_at",      "value": now.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
         "updated_at": datetime.datetime.utcnow().isoformat() + "Z"},
        {"key": "last_updated_display", "value": now.strftime("%d %b %Y, %H:%M WIB"),
         "updated_at": datetime.datetime.utcnow().isoformat() + "Z"},
        {"key": "fetch_status",         "value": status,
         "updated_at": datetime.datetime.utcnow().isoformat() + "Z"},
        {"key": "news_count",           "value": str(news_count),
         "updated_at": datetime.datetime.utcnow().isoformat() + "Z"},
        {"key": "ideas_count",          "value": str(ideas_count),
         "updated_at": datetime.datetime.utcnow().isoformat() + "Z"},
        {"key": "fetch_ts",             "value": str(int(time.time())),
         "updated_at": datetime.datetime.utcnow().isoformat() + "Z"},
    ]
    sb_post("app_meta", rows)
    print(f"  ✓ app_meta: updated at {now.strftime('%H:%M WIB')}")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_SERVICE_KEY not set.")
        raise SystemExit(1)

    now = now_wib()
    print(f"\n{'='*55}")
    print(f"  MUFG Indonesia Morning Brief — Data Fetch")
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S WIB')}")
    print(f"{'='*55}\n")

    syms = list(YAHOO_SYMBOLS.keys())
    print(f"1/5  Fetching {len(syms)} Yahoo Finance quotes...")
    quotes = fetch_yahoo_batch(syms)
    market_rows = write_market_data(quotes)

    print("2/5  Fetching FRED US Treasury yield curve...")
    yields = fetch_fred_yields()
    write_yield_curve(yields)

    print("3/5  Fetching RSS news feeds...")
    news = fetch_all_news()
    write_news(news)

    print("4/5  Generating client ideas...")
    ideas = generate_client_ideas(market_rows, news)
    write_client_ideas(ideas)

    print("5/5  Fetching MUFG Research articles...")
    articles = fetch_mufg_research()
    write_mufg_research(articles)

    write_app_meta("ok", len(news), len(ideas))

    print(f"\n✅ Done — {len(news)} news, {len(ideas)} ideas, {len(articles)} MUFG articles\n")

if __name__ == "__main__":
    main()
