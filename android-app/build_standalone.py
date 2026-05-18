#!/usr/bin/env python3
"""
build_standalone.py
-------------------
Reads ../index.html and produces app/src/main/assets/index.html
with all Supabase/GitHub dependencies removed. The resulting page
fetches market data directly from Yahoo Finance (via allorigins.win
CORS proxy), yield curve from FRED, and news from public RSS feeds.

Run from the android-app/ directory:
    python build_standalone.py
"""

import os
import re

SRC  = os.path.join(os.path.dirname(__file__), '..', 'index.html')
DEST = os.path.join(os.path.dirname(__file__), 'app', 'src', 'main', 'assets', 'index.html')

# ── Patches ─────────────────────────────────────────────────────────────────

# 1. Updated CSP — keeps allorigins.win, FRED, Yahoo Finance; removes Supabase
OLD_CSP = 'content="default-src \'self\'; script-src \'self\' \'unsafe-inline\' https://cdn.jsdelivr.net; style-src \'self\' \'unsafe-inline\'; img-src \'self\' data:; font-src \'self\' data:; connect-src \'self\' https://*.supabase.co https://api.github.com https://api.allorigins.win; base-uri \'self\'; form-action \'self\'; frame-ancestors \'none\'; object-src \'none\'"'
NEW_CSP = 'content="default-src \'self\' https://appassets.androidplatform.net; script-src \'self\' \'unsafe-inline\' https://cdn.jsdelivr.net https://appassets.androidplatform.net; style-src \'self\' \'unsafe-inline\'; img-src \'self\' data:; font-src \'self\' data:; connect-src \'self\' https://appassets.androidplatform.net https://api.allorigins.win https://fred.stlouisfed.org https://query1.finance.yahoo.com https://finance.yahoo.com https://*.supabase.co https://api.github.com; base-uri \'self\'; form-action \'self\'; frame-ancestors \'none\'; object-src \'none\'"'

# 2. Remove Supabase SDK — entire script tag
SUPABASE_SDK_LINE = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.99.2/dist/umd/supabase.min.js" integrity="sha384-zETTH+6IXxKQ6zbGcT6H6EDdnGaae9uhI8uO7doTJoNEmPGeTKVOe5S6/XybS9JH" crossorigin="anonymous"></script>'

# 3. Replace initSupabase + old DOMContentLoaded with standalone init
OLD_INIT = '''document.addEventListener('DOMContentLoaded', () => {
  setGreeting();
  loadSettings();
  loadNotes();
  renderDefaultSources();
  renderCustomSources();
  updateRefreshVisibility();
  const cfg = getConfig();
  if(cfg.url && cfg.anon){
    // Auto-connect: site credentials or admin localStorage override
    initSupabase(cfg.url, cfg.anon);
    loadAll();
  } else {
    // Only show setup modal if site credentials haven't been filled in yet
    document.getElementById('setupModal').classList.add('show');
  }
});'''

NEW_INIT = '''document.addEventListener('DOMContentLoaded', () => {
  setGreeting();
  loadNotes();
  renderDefaultSources();
  renderCustomSources();
  // Standalone mode: fetch directly, no Supabase required
  loadAllDirect();
});'''

# 4. Replace initSupabase function (stub it out)
OLD_INIT_SB = '''function initSupabase(url, anon){
  try {
    SB = supabase.createClient(url, anon);
    document.getElementById('sb-status').className='conn-badge conn-ok';
    document.getElementById('sb-status').innerHTML='<span class="conn-dot ok"></span>Connected';
    // Real-time: reload when app_meta changes (fetch completed)
    SB.channel('meta_changes')
      .on('postgres_changes',{event:'UPDATE',schema:'public',table:'app_meta'},() => {
        console.log('Supabase: new data detected, reloading...');
        setTimeout(loadAll, 1000);
      }).subscribe();
  } catch(e){
    console.error('Supabase init error:',e);
    document.getElementById('sb-status').innerHTML='<span class="conn-dot err"></span>Error';
  }
}'''

NEW_INIT_SB = '''function initSupabase(url, anon){
  // Standalone mode — Supabase not used
}'''

# 5. Replace loadAll with loadAllDirect (injected below)
OLD_LOADALL_OPEN = '''// ── Load all data ────────────────────────────────────────────────────────
async function loadAll(){
  if(!SB) return;
  try {
    const [meta, market, yields, news, ideas, mufg, flagged] = await Promise.all([
      SB.from('app_meta').select('*'),
      SB.from('market_data').select('*'),
      SB.from('yield_curve').select('*').order('id'),
      SB.from('news_items').select('*').order('created_at',{ascending:false}).limit(80),
      SB.from('client_ideas').select('*'),
      SB.from('mufg_research').select('*').order('id',{ascending:false}),
      SB.from('flagged_articles').select('*').order('flagged_at',{ascending:false}),
    ]);

    const metaMap = {};
    (meta.data||[]).forEach(r => metaMap[r.key]=r.value);

    document.getElementById('hdr-updated').textContent = metaMap['last_updated_display'] || '–';
    const refreshedDisplay = metaMap['last_updated_display'] || '–';
    const elOvTime = document.getElementById('ov-refreshed-time'); if(elOvTime) elOvTime.textContent = refreshedDisplay;
    const elMktTime = document.getElementById('mkt-refreshed-time'); if(elMktTime) elMktTime.textContent = refreshedDisplay;
    document.getElementById('ft-updated').textContent  = 'Last updated: ' + (metaMap['last_updated_display']||'–');
    document.getElementById('src-last-fetch').textContent = metaMap['last_updated_display']||'–';
    document.getElementById('src-news-count').textContent = metaMap['news_count']||'0';
    const status = metaMap['fetch_status']||'unknown';
    document.getElementById('hdr-status').textContent = status === 'ok' ? '✓ Fetch OK' : '⚠ '+status;
    document.getElementById('hdr-status').className   = status==='ok'?'text-green':'text-amber';

    // Store ISO timestamp for live "X min ago" counter
    window._lastFetchedISO = metaMap['last_updated_at'] || null;
    updateAgo();

    const mkt  = market.data||[];
    const ylds = yields.data||[];
    ALL_MARKET  = mkt;
    ALL_NEWS    = news.data||[];
    ALL_IDEAS   = ideas.data||[];
    ALL_MUFG    = mufg.data||[];
    ALL_FLAGGED = flagged.data||[];
    FLAGGED_IDS = new Set(ALL_FLAGGED.map(f=>f.id));

    renderKPIs(mkt);
    renderAlerts(mkt);
    renderMovers(mkt);
    renderTables(mkt);
    renderYieldCurve(ylds);
    renderRatesRow(ylds);
    renderNDFandCCS(mkt, ylds);
    renderIDR(mkt);
    renderIDNews();
    renderNews();
    renderIdeas();
    renderSectorImpact();
    renderSegmentNotes();
    renderChartOfDay();
    renderMufgArticles();
    renderOvNews();
    renderOvPriorities();
    renderOvSectors();
    renderFlagged();
  } catch(e){
    console.error('loadAll error:',e);
    document.getElementById('hdr-status').textContent = '⚠ Load error — check Supabase config';
    document.getElementById('hdr-status').className   = 'text-red';
  }
}'''

DIRECT_FETCH_CODE = '''// ── Standalone direct-fetch mode — no Supabase ──────────────────────────

// Symbol metadata (mirrors fetch_data.py YAHOO_SYMBOLS)
const DIRECT_SYMBOLS = {
  'BZ=F':      {name:'Brent Crude',    unit:'USD/bbl',   category:'energy'},
  'CL=F':      {name:'WTI Crude',      unit:'USD/bbl',   category:'energy'},
  'NG=F':      {name:'Natural Gas',    unit:'USD/MMBtu', category:'energy'},
  'GC=F':      {name:'Gold',           unit:'USD/oz',    category:'metals'},
  'SI=F':      {name:'Silver',         unit:'USD/oz',    category:'metals'},
  'HG=F':      {name:'Copper',         unit:'USD/lb',    category:'metals'},
  'ZW=F':      {name:'Wheat',          unit:'USc/bu',    category:'agricultural'},
  'ZS=F':      {name:'Soybeans',       unit:'USc/bu',    category:'agricultural'},
  'IDR=X':     {name:'USD/IDR',        unit:'Rp',        category:'fx'},
  'SGD=X':     {name:'USD/SGD',        unit:'SGD',       category:'fx'},
  'EURUSD=X':  {name:'EUR/USD',        unit:'USD',       category:'fx'},
  'JPY=X':     {name:'USD/JPY',        unit:'¥',         category:'fx'},
  'CNY=X':     {name:'USD/CNY',        unit:'CNY',       category:'fx'},
  'MYR=X':     {name:'USD/MYR',        unit:'MYR',       category:'fx'},
  'DX-Y.NYB':  {name:'DXY Index',      unit:'',          category:'fx'},
  '^GSPC':     {name:'S&P 500',        unit:'',          category:'equities'},
  '^IXIC':     {name:'Nasdaq',         unit:'',          category:'equities'},
  '^DJI':      {name:'Dow Jones',      unit:'',          category:'equities'},
  '^STI':      {name:'SGX STI',        unit:'',          category:'equities'},
  '^JKSE':     {name:'IDX Composite',  unit:'',          category:'equities'},
  '^N225':     {name:'Nikkei 225',     unit:'',          category:'equities'},
  '^HSI':      {name:'Hang Seng',      unit:'',          category:'equities'},
  '^TNX':      {name:'US 10Y Yield',   unit:'%',         category:'rates_spot'},
  '^FVX':      {name:'US 5Y Yield',    unit:'%',         category:'rates_spot'},
  '^TYX':      {name:'US 30Y Yield',   unit:'%',         category:'rates_spot'},
};

// FRED series for yield curve
const FRED_TENORS = [
  {id:'DGS1MO',  label:'1M',  tenor:1},
  {id:'DGS3MO',  label:'3M',  tenor:2},
  {id:'DGS6MO',  label:'6M',  tenor:3},
  {id:'DGS1',    label:'1Y',  tenor:4},
  {id:'DGS2',    label:'2Y',  tenor:5},
  {id:'DGS5',    label:'5Y',  tenor:6},
  {id:'DGS10',   label:'10Y', tenor:7},
  {id:'DGS20',   label:'20Y', tenor:8},
  {id:'DGS30',   label:'30Y', tenor:9},
];

// RSS sources (same defaults as fetch_data.py)
const DIRECT_RSS = [
  {name:'Reuters Business',  url:'https://feeds.reuters.com/reuters/businessNews',              cat:'markets'},
  {name:'Reuters World',     url:'https://feeds.reuters.com/reuters/worldNews',                 cat:'global'},
  {name:'Yahoo Finance',     url:'https://finance.yahoo.com/rss/topstories',                   cat:'markets'},
  {name:'CNBC Top News',     url:'https://www.cnbc.com/id/100003114/device/rss/rss.html',      cat:'markets'},
  {name:'Jakarta Post',      url:'https://www.thejakartapost.com/rss/id/business.xml',         cat:'indonesia'},
  {name:'Antara News',       url:'https://www.antaranews.com/rss/economics.xml',               cat:'indonesia'},
  {name:'EIA News',          url:'https://www.eia.gov/rss/news.xml',                           cat:'energy'},
];

const PROXY = 'https://api.allorigins.win/raw?url=';

async function fetchViaProxy(url) {
  const r = await fetch(PROXY + encodeURIComponent(url), {signal: AbortSignal.timeout(12000)});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.text();
}

async function fetchYahooQuotes() {
  const syms = Object.keys(DIRECT_SYMBOLS).join(',');
  const apiUrl = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(syms)}&fields=regularMarketPrice,regularMarketChangePercent,regularMarketChange,regularMarketPreviousClose,shortName`;
  const raw = await fetchViaProxy(apiUrl);
  const data = JSON.parse(raw);
  const results = data?.quoteResponse?.result || [];
  return results.map(q => {
    const meta = DIRECT_SYMBOLS[q.symbol] || {};
    const price  = q.regularMarketPrice || 0;
    const prev   = q.regularMarketPreviousClose || price;
    const chgPct = q.regularMarketChangePercent || 0;
    const chgAbs = q.regularMarketChange || 0;
    return {
      symbol:      q.symbol,
      name:        meta.name || q.shortName || q.symbol,
      price,
      change_pct:  chgPct,
      change_abs:  chgAbs,
      prev_close:  prev,
      currency:    q.currency || 'USD',
      unit:        meta.unit || '',
      category:    meta.category || 'other',
      subcategory: meta.category || 'other',
    };
  });
}

async function fetchFredYields() {
  const results = await Promise.allSettled(
    FRED_TENORS.map(async t => {
      const url = `https://fred.stlouisfed.org/graph/fredgraph.csv?id=${t.id}`;
      const txt = await (await fetch(url, {signal: AbortSignal.timeout(10000)})).text();
      const lines = txt.trim().split('\\n').filter(l => l && !l.startsWith('DATE'));
      const last  = lines[lines.length - 1];
      const val   = last ? parseFloat(last.split(',')[1]) : null;
      return {...t, yield_pct: isNaN(val) ? null : val};
    })
  );
  return results
    .filter(r => r.status === 'fulfilled')
    .map(r => r.value)
    .filter(r => r.yield_pct !== null);
}

function parseRssXml(xml, source, cat) {
  try {
    const doc = new DOMParser().parseFromString(xml, 'text/xml');
    const items = Array.from(doc.querySelectorAll('item')).slice(0, 12);
    const now   = new Date().toISOString();
    return items.map((item, i) => {
      const title   = item.querySelector('title')?.textContent?.trim() || '';
      const link    = item.querySelector('link')?.textContent?.trim() ||
                      item.querySelector('guid')?.textContent?.trim() || '#';
      const summary = item.querySelector('description')?.textContent
                          ?.replace(/<[^>]+>/g,'').trim().slice(0, 300) || '';
      const pubDate = item.querySelector('pubDate')?.textContent?.trim() || now;
      const idStr   = (source + title).toLowerCase().replace(/[^a-z0-9]/g,'').slice(0,12);
      const idn     = /indonesia|jakarta|rupiah|bi rate|jkse|idr|bpjs|bnpb|pertamina|pln|garuda/i.test(title+summary);
      const iscorr  = /corrupt|kpk|suap|tipikor|fraud/i.test(title+summary);
      return {
        id:            idStr.padEnd(12,'0').slice(0,12),
        title,
        url:           link,
        summary,
        source,
        category:      cat,
        is_indonesia:  idn,
        is_corruption: iscorr,
        created_at:    new Date(pubDate).toISOString() || now,
      };
    });
  } catch(e) {
    return [];
  }
}

async function fetchAllNews() {
  const feeds = [...DIRECT_RSS];
  // Merge user-saved custom sources from localStorage
  try {
    const saved = JSON.parse(localStorage.getItem('standalone_sources') || '[]');
    feeds.push(...saved.filter(s => s.enabled !== false));
  } catch(e) {}

  const results = await Promise.allSettled(
    feeds.map(async f => {
      const xml = await fetchViaProxy(f.url);
      return parseRssXml(xml, f.name, f.cat || 'markets');
    })
  );
  const articles = results
    .filter(r => r.status === 'fulfilled')
    .flatMap(r => r.value);
  // Deduplicate by id
  const seen = new Set();
  return articles.filter(a => {
    if (seen.has(a.id)) return false;
    seen.add(a.id);
    return true;
  }).sort((a,b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 80);
}

function generateIdeas(mkt) {
  const q = {};
  mkt.forEach(r => { q[r.symbol] = r; });
  const ideas = [];
  let id = 1;

  const add = (priority, title, sector, idea, segment) =>
    ideas.push({id: String(id++), priority, title, sector, idea, segment});

  const brent = q['BZ=F']?.change_pct || 0;
  if (brent >= 1.5)  add('CRITICAL','Brent +'+(brent.toFixed(1))+'%','Energy','Upstream energy cost alert for energy-intensive sectors','corporate');
  if (brent <= -1.5) add('HIGH','Brent '+(brent.toFixed(1))+'%','Energy','Downstream/consumer sector opportunity on lower fuel costs','corporate');

  const idr = q['IDR=X']?.price || 0;
  const idrChg = q['IDR=X']?.change_pct || 0;
  if (idr >= 16500)  add('HIGH','USD/IDR at '+idr.toLocaleString(),'FX','IDR weakness — hedging alert for corporates with USD exposure','fx');
  if (idrChg >= 1.0) add('CRITICAL','IDR weakened '+idrChg.toFixed(1)+'% today','FX','IDR sharp move — urgent RM discussion needed','fx');

  const gas = q['NG=F']?.change_pct || 0;
  if (gas >= 2.0)    add('HIGH','Natural Gas +'+(gas.toFixed(1))+'%','Energy','Gas/LNG pricing alert for utilities and fertiliser clients','corporate');

  const jkse = q['^JKSE']?.change_pct || 0;
  if (Math.abs(jkse) >= 1.0) add('MEDIUM','IDX '+(jkse>0?'+':'')+jkse.toFixed(1)+'%','Equities','IDX equity market move — equity-linked product discussion','equities');

  const sp = q['^GSPC']?.change_pct || 0;
  if (sp <= -1.5)    add('HIGH','S&P 500 '+(sp.toFixed(1))+'%','Equities','US risk-off — discuss capital flows and hedging with clients','macro');

  const gold = q['GC=F']?.change_pct || 0;
  if (gold >= 1.5)   add('MEDIUM','Gold +'+(gold.toFixed(1))+'%','Metals','Safe-haven demand rising — review client hedging positions','metals');

  return ideas;
}

async function loadAllDirect() {
  const nowISO = new Date().toISOString();
  const nowDisplay = new Date().toLocaleString('en-GB', {
    day:'2-digit', month:'short', year:'numeric',
    hour:'2-digit', minute:'2-digit', timeZoneName:'short'
  });

  document.getElementById('hdr-status').textContent = '↻ Loading…';
  document.getElementById('hdr-status').className   = 'text-amber';

  try {
    const [mkt, ylds, news] = await Promise.all([
      fetchYahooQuotes().catch(e => { console.warn('Quotes error:', e); return []; }),
      fetchFredYields().catch(e => { console.warn('FRED error:', e); return []; }),
      fetchAllNews().catch(e => { console.warn('News error:', e); return []; }),
    ]);

    const ideas   = generateIdeas(mkt);
    ALL_MARKET    = mkt;
    ALL_NEWS      = news;
    ALL_IDEAS     = ideas;
    ALL_MUFG      = [];
    ALL_FLAGGED   = loadLocalFlagged();
    FLAGGED_IDS   = new Set(ALL_FLAGGED.map(f => f.id));

    // Update header timestamps
    document.getElementById('hdr-updated').textContent   = nowDisplay;
    document.getElementById('ft-updated').textContent    = 'Last updated: ' + nowDisplay;
    document.getElementById('src-last-fetch').textContent = nowDisplay;
    document.getElementById('src-news-count').textContent = String(news.length);
    document.getElementById('hdr-status').textContent    = '✓ Live data';
    document.getElementById('hdr-status').className      = 'text-green';

    const elOvTime  = document.getElementById('ov-refreshed-time');  if(elOvTime)  elOvTime.textContent  = nowDisplay;
    const elMktTime = document.getElementById('mkt-refreshed-time'); if(elMktTime) elMktTime.textContent = nowDisplay;

    window._lastFetchedISO = nowISO;
    updateAgo();

    renderKPIs(mkt);
    renderAlerts(mkt);
    renderMovers(mkt);
    renderTables(mkt);
    renderYieldCurve(ylds);
    renderRatesRow(ylds);
    renderNDFandCCS(mkt, ylds);
    renderIDR(mkt);
    renderIDNews();
    renderNews();
    renderIdeas();
    renderSectorImpact();
    renderSegmentNotes();
    renderChartOfDay();
    renderMufgArticles();
    renderOvNews();
    renderOvPriorities();
    renderOvSectors();
    renderFlagged();

  } catch(e) {
    console.error('loadAllDirect error:', e);
    document.getElementById('hdr-status').textContent = '⚠ Load error';
    document.getElementById('hdr-status').className   = 'text-red';
  }
}

// Stub original loadAll — used by Refresh button if present
async function loadAll() { return loadAllDirect(); }

// ── Local-storage backed flagged articles (replaces Supabase writes) ───────
function loadLocalFlagged() {
  try { return JSON.parse(localStorage.getItem('standalone_flagged') || '[]'); } catch(e) { return []; }
}
function saveLocalFlagged(arr) {
  localStorage.setItem('standalone_flagged', JSON.stringify(arr));
}
async function flagArticle(n) {
  const id = safeId(n.id || Math.random().toString(36).slice(2,14));
  const row = {
    id, title: n.title, url: n.url, source: n.source,
    risk_headline: n.title, risk_level: 'MEDIUM',
    flagged_at: new Date().toISOString(),
    is_processed: false,
  };
  const arr = loadLocalFlagged().filter(f => f.id !== id);
  arr.unshift(row);
  saveLocalFlagged(arr.slice(0,100));
  ALL_FLAGGED = loadLocalFlagged();
  FLAGGED_IDS = new Set(ALL_FLAGGED.map(f => f.id));
  renderFlagged();
}
async function unflagArticle(id) {
  const arr = loadLocalFlagged().filter(f => f.id !== id);
  saveLocalFlagged(arr);
  ALL_FLAGGED = arr;
  FLAGGED_IDS = new Set(ALL_FLAGGED.map(f => f.id));
  renderFlagged();
}
async function toggleFlag(id) {
  if (FLAGGED_IDS.has(id)) {
    await unflagArticle(id);
  } else {
    const n = ALL_NEWS.find(x => x.id === id);
    if (n) await flagArticle(n);
  }
  renderNews();
}

// ── Local-storage backed custom sources ─────────────────────────────────────
async function addCustomSource() {
  const name = document.getElementById('src-new-name')?.value?.trim() || '';
  const url  = document.getElementById('src-new-url')?.value?.trim()  || '';
  const cat  = document.getElementById('src-new-cat')?.value || 'markets';
  if (!url) { alert('Enter a URL'); return; }
  try {
    const u = new URL(url);
    if (u.protocol !== 'https:') { alert('URL must start with https://'); return; }
    if (url.length >= 500)        { alert('URL too long (max 500 chars)'); return; }
    if (name.length >= 200)       { alert('Name too long (max 200 chars)'); return; }
  } catch { alert('Invalid URL — enter a full https:// address'); return; }

  const saved = JSON.parse(localStorage.getItem('standalone_sources') || '[]');
  const id = Math.random().toString(36).slice(2,14);
  saved.push({id, name: name||url, url, cat, enabled: true, added_at: new Date().toISOString()});
  localStorage.setItem('standalone_sources', JSON.stringify(saved));
  if (document.getElementById('src-new-name')) document.getElementById('src-new-name').value = '';
  if (document.getElementById('src-new-url'))  document.getElementById('src-new-url').value  = '';
  renderCustomSources();
  loadAllDirect();
}
function toggleSource(id, val) {
  const saved = JSON.parse(localStorage.getItem('standalone_sources') || '[]');
  const idx = saved.findIndex(s => s.id === id);
  if (idx >= 0) { saved[idx].enabled = val; localStorage.setItem('standalone_sources', JSON.stringify(saved)); }
}
function deleteSource(id) {
  const saved = JSON.parse(localStorage.getItem('standalone_sources') || '[]').filter(s => s.id !== id);
  localStorage.setItem('standalone_sources', JSON.stringify(saved));
  renderCustomSources();
}
function renderCustomSources() {
  const el = document.getElementById('custom-sources-list');
  if (!el) return;
  const saved = JSON.parse(localStorage.getItem('standalone_sources') || '[]');
  if (!saved.length) { el.innerHTML = '<p style="color:var(--muted);font-size:12px">No custom sources added yet.</p>'; return; }
  el.innerHTML = saved.map(s => `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border)">
      <input type="checkbox" ${s.enabled!==false?'checked':''} onchange="toggleSource('${safeId(s.id)}',this.checked)">
      <div style="flex:1;min-width:0">
        <div style="font-size:12px;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.name)}</div>
        <div style="font-size:10px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.url)}</div>
      </div>
      <button class="btn-ghost" style="font-size:11px;padding:3px 8px" onclick="deleteSource('${safeId(s.id)}')">Remove</button>
    </div>`).join('');
}'''

# ── Supabase write stubs to silence errors if old functions are called ────────
OLD_SB_WRITE_ADD = '''async function addCustomSource(){
  const name = document.getElementById('src-new-name')?.value?.trim()||'';
  const url  = document.getElementById('src-new-url')?.value?.trim()||'';
  const cat  = document.getElementById('src-new-cat')?.value||'markets';
  if(!url){alert('Enter a URL');return;}
  try{
    const u = new URL(url);
    if(u.protocol!=='https:'){alert('RSS URL must start with https://');return;}
    if(url.length>=500){alert('URL is too long (max 500 chars)');return;}
    if(name.length>=200){alert('Name is too long (max 200 chars)');return;}
  }catch{alert('Invalid URL — please enter a full https:// address');return;}
  if(!SB){alert('Connect to Supabase first');return;}'''

# Mark we just want to skip this block — we replace the entire function above
# (the script replaces loadAll block which already injected addCustomSource)

def apply_patches(html: str) -> str:
    patches = [
        (OLD_CSP, NEW_CSP, 'CSP'),
        (SUPABASE_SDK_LINE, '<!-- Supabase SDK removed: standalone mode fetches directly -->', 'Supabase SDK'),
        (OLD_INIT, NEW_INIT, 'DOMContentLoaded init'),
        (OLD_INIT_SB, NEW_INIT_SB, 'initSupabase stub'),
        (OLD_LOADALL_OPEN, DIRECT_FETCH_CODE, 'loadAll → loadAllDirect'),
    ]

    for old, new, name in patches:
        if old in html:
            html = html.replace(old, new, 1)
            print(f'  ✓ Patched: {name}')
        else:
            print(f'  ⚠ NOT FOUND (check for drift): {name}')

    # Remove standalone addCustomSource / toggleSource / deleteSource / renderCustomSources
    # that exist in the original file — our injected version above replaces them.
    # We blank them out rather than deleting to preserve line structure.
    sb_funcs_to_stub = [
        ('async function addCustomSource()',
         'async function deleteSource(id)',
         'addCustomSource/toggleSource/deleteSource original'),
    ]
    # Use regex to find and stub the original addCustomSource block
    pattern = r'async function addCustomSource\(\)\{.*?^(?=async function deleteSource|\nasync function renderCustom)'
    html = re.sub(
        r'(async function addCustomSource\(\)\{[^}]*\}[^}]*\}[^}]*\})',
        '/* addCustomSource replaced by standalone version */',
        html, count=1, flags=re.DOTALL
    )

    # Stub original flagArticle / unflagArticle / toggleFlag
    html = re.sub(
        r'(async function flagArticle\(n\)\{.*?^(?=async function unflagArticle))',
        '',
        html, count=1, flags=re.DOTALL
    )
    html = re.sub(
        r'(async function unflagArticle\(id\)\{.*?^(?=async function toggleFlag))',
        '',
        html, count=1, flags=re.DOTALL
    )
    html = re.sub(
        r'(async function toggleFlag\(id\)\{.*?^(?=async function showFlagged))',
        '',
        html, count=1, flags=re.DOTALL
    )

    return html

if __name__ == '__main__':
    print(f'Reading {SRC}')
    with open(SRC, 'r', encoding='utf-8') as f:
        html = f.read()

    print(f'Applying patches...')
    patched = apply_patches(html)

    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    with open(DEST, 'w', encoding='utf-8') as f:
        f.write(patched)

    size_kb = os.path.getsize(DEST) // 1024
    print(f'\\nWrote {DEST} ({size_kb} KB)')
    print('\\nNext step: open android-app/ in Android Studio → Build → Generate Signed APK')
