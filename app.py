import io, re, datetime
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="US Momentum Scanner", page_icon="🚀", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.5rem;}
@media (max-width: 800px) {
  .block-container {padding-left: .7rem; padding-right: .7rem;}
  div[data-testid="stDataFrame"] {font-size: 11px;}
}
</style>
""", unsafe_allow_html=True)

def clean_ticker(x):
    x = str(x).strip().upper().replace(".", "-")
    return x if re.fullmatch(r"[A-Z0-9-]{1,12}", x) else None

@st.cache_data(ttl=3600)
def load_local_universe():
    result = {}
    for name in ["sp500", "nasdaq100", "russell2000", "all_unique"]:
        p = DATA / f"{name}.txt"
        if p.exists():
            vals = []
            for line in p.read_text(encoding="utf-8").splitlines():
                t = clean_ticker(line)
                if t and not line.startswith("#"):
                    vals.append(t)
            result[name] = sorted(set(vals))
        else:
            result[name] = []
    return result

@st.cache_data(ttl=3600)
def refresh_online_lists():
    """Best-effort refresh. The app remains functional if a source is unavailable."""
    out = {}
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        t = next(x for x in tables if "Symbol" in x.columns)
        out["sp500"] = sorted({clean_ticker(x) for x in t["Symbol"] if clean_ticker(x)})
    except Exception:
        out["sp500"] = []
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        vals = []
        for t in tables:
            for col in ["Ticker", "Symbol"]:
                if col in t.columns:
                    vals.extend(clean_ticker(x) for x in t[col])
        out["nasdaq100"] = sorted({x for x in vals if x})
    except Exception:
        out["nasdaq100"] = []
    try:
        url = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/latest-holdings.csv"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=45)
        lines = r.text.splitlines()
        idx = next(i for i, line in enumerate(lines) if line.startswith("Ticker,Name,"))
        df = pd.read_csv(io.StringIO("\n".join(lines[idx:])))
        if "Asset Class" in df.columns:
            df = df[df["Asset Class"].astype(str).str.lower().eq("equity")]
        out["russell2000"] = sorted({clean_ticker(x) for x in df["Ticker"] if clean_ticker(x)})
    except Exception:
        out["russell2000"] = []
    return out

def build_universe(local, choice, online_refresh=False):
    src = local.copy()
    if online_refresh:
        online = refresh_online_lists()
        for k, v in online.items():
            if len(v) > len(src.get(k, [])):
                src[k] = v
    if choice == "S&P 500":
        vals = src["sp500"]
    elif choice == "Nasdaq-100":
        vals = src["nasdaq100"]
    elif choice == "Russell 2000":
        vals = src["russell2000"]
    else:
        vals = sorted(set(src["sp500"]) | set(src["nasdaq100"]) | set(src["russell2000"]))
    return sorted(set(vals) | {"SPY", "QQQ"}), src

@st.cache_data(ttl=300, show_spinner=False)
def download_data(tickers):
    return yf.download(
        tickers=list(tickers), period="1y", interval="1d",
        auto_adjust=True, progress=False, threads=True, group_by="column"
    )

def get_series(df, field, ticker):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            return df[field][ticker]
        return df[field]
    except Exception:
        return pd.Series(dtype=float)

def scanner(prices, volumes, spy_close):
    rows = []
    for ticker in prices.columns:
        s = prices[ticker].dropna()
        v = volumes[ticker].dropna() if ticker in volumes.columns else pd.Series(dtype=float)
        if len(s) < 65:
            continue
        last = float(s.iloc[-1])
        if not np.isfinite(last) or last <= 0:
            continue
        def ret(n):
            return float(s.iloc[-1] / s.iloc[-n-1] - 1) if len(s) > n else np.nan
        ma20 = s.rolling(20).mean().iloc[-1]
        ma50 = s.rolling(50).mean().iloc[-1]
        ma200 = s.rolling(200).mean().iloc[-1] if len(s) >= 200 else np.nan
        avgvol = v.rolling(20).mean().iloc[-1] if len(v) else np.nan
        volratio = float(v.iloc[-1] / avgvol) if avgvol and np.isfinite(avgvol) and avgvol > 0 else np.nan
        high20 = s.rolling(20).max().iloc[-1]
        high252 = s.tail(252).max()
        dist52 = float(last / high252 - 1)
        breakout20 = last >= high20 * .998
        near52 = dist52 >= -.03
        r5, r20 = ret(5), ret(20)
        accel = r5 - r20/4 if np.isfinite(r5) and np.isfinite(r20) else np.nan
        spy5 = float(spy_close.iloc[-1] / spy_close.iloc[-6] - 1) if len(spy_close) > 5 else np.nan
        spy20 = float(spy_close.iloc[-1] / spy_close.iloc[-21] - 1) if len(spy_close) > 20 else np.nan
        rs5, rs20 = r5-spy5, r20-spy20
        trend = np.nanmean([
            1 if last > ma20 else 0,
            1 if last > ma50 else 0,
            1 if np.isfinite(ma200) and last > ma200 else 0,
            1 if ma20 > ma50 else 0
        ]) * 100
        mom = np.nanmean([ret(1)*100, r5*100, r20*100, ret(60)*100])
        volscore = min(max((volratio-1)*25+50, 0), 100) if np.isfinite(volratio) else 0
        breakout = 100 if breakout20 else (80 if near52 else max(0, 50 + dist52*100))
        accscore = min(max(50 + accel*200, 0), 100) if np.isfinite(accel) else 50
        rsscore = min(max(50 + np.nanmean([rs5, rs20])*200, 0), 100)
        final = .25*mom + .20*rsscore + .20*volscore + .15*breakout + .10*trend + .10*accscore
        setup = "🚀 Explosiv" if final >= 75 and volratio >= 1.5 and (breakout20 or near52) else (
            "🔥 Stark" if final >= 65 else ("⚡ Momentum" if final >= 55 else "Normal"))
        rows.append({
            "Ticker": ticker, "Score": round(final,1), "Setup": setup,
            "1D %": round(ret(1)*100,2), "5D %": round(r5*100,2),
            "20D %": round(r20*100,2), "60D %": round(ret(60)*100,2),
            "Vol x": round(volratio,2) if np.isfinite(volratio) else np.nan,
            "52W": round(dist52*100,2), "RS 20D": round(rs20*100,2),
            "Trend": round(trend,0), "Accel": round(accel*100,2) if np.isfinite(accel) else np.nan,
            "Price": round(last,2)
        })
    return pd.DataFrame(rows).sort_values("Score", ascending=False)

st.title("🚀 US Momentum Scanner")
st.caption("S&P 500 + Nasdaq-100 + Russell 2000/IWM universe • technische Signale • kein Anlage-Rat")

local = load_local_universe()
with st.sidebar:
    st.header("Universe")
    choice = st.selectbox("Aktienuniversum", ["Alle 3 Indizes", "S&P 500", "Nasdaq-100", "Russell 2000"])
    refresh_online = st.checkbox("Indexlisten online aktualisieren", value=False)
    min_price = st.number_input("Mindestpreis ($)", min_value=0.0, value=3.0, step=1.0)
    min_score = st.slider("Mindest-Score", 0, 100, 45)
    max_results = st.slider("Anzahl Ergebnisse", 10, 200, 50, 10)
    if st.button("🔄 Marktdaten aktualisieren"):
        download_data.clear()
        st.rerun()

tickers, source = build_universe(local, choice, refresh_online)
st.info(f"Universe: **{len(tickers)-2:,} Aktien/Ticker** • lokale Listen aktiv • Daten via Yahoo Finance/yfinance")

raw = download_data(tuple(tickers))
close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw["Close"]
vol = raw["Volume"] if isinstance(raw.columns, pd.MultiIndex) else raw["Volume"]

if "SPY" not in close.columns:
    st.error("SPY-Daten konnten nicht geladen werden.")
    st.stop()

spy = close["SPY"].dropna()
stocks = [t for t in tickers if t not in {"SPY","QQQ"} and t in close.columns]
result = scanner(close[stocks], vol[stocks], spy)
result = result[result["Price"] >= min_price]
result = result[result["Score"] >= min_score]

c1,c2,c3,c4 = st.columns(4)
c1.metric("Scanned", f"{len(result):,}")
c2.metric("Explosive Setups", f"{(result['Setup']=='🚀 Explosiv').sum():,}")
c3.metric("Ø Score", f"{result['Score'].mean():.1f}" if len(result) else "—")
c4.metric("Volumen > 2x", f"{(result['Vol x']>=2).sum():,}")

tabs = st.tabs(["🚀 Top Momentum", "💥 Explosive Setups", "📈 Relative Strength", "📊 Volume Surges"])
with tabs[0]:
    st.dataframe(result.head(max_results), use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(result[result["Setup"]=="🚀 Explosiv"].head(max_results), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(result.sort_values("RS 20D", ascending=False).head(max_results), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(result.sort_values("Vol x", ascending=False).head(max_results), use_container_width=True, hide_index=True)

with st.expander("Alle gescannten Aktien"):
    st.dataframe(result, use_container_width=True, hide_index=True)

st.caption(f"Stand: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} • Yahoo Finance/yfinance kann verzögerte oder unvollständige Daten liefern.")
