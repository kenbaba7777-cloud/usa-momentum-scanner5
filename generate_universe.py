from pathlib import Path
import io, re, requests, pandas as pd

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"
DATA.mkdir(exist_ok=True)

def clean(x):
    x=str(x).strip().upper().replace(".","-")
    return x if re.fullmatch(r"[A-Z0-9-]{1,12}",x) else None

def save(name, vals, note):
    vals=sorted({x for x in (clean(v) for v in vals) if x})
    (DATA/name).write_text(note+"\n"+"\n".join(vals)+"\n",encoding="utf-8")
    return vals

sp=pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
sp=next(t for t in sp if "Symbol" in t.columns)
a=save("sp500.txt",sp["Symbol"],"# S&P 500 current web list")

nd=pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
vals=[]
for t in nd:
    for c in ("Ticker","Symbol"):
        if c in t.columns: vals += list(t[c])
b=save("nasdaq100.txt",vals,"# Nasdaq-100 current web list")

url="https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/latest-holdings.csv"
r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=60)
lines=r.text.splitlines()
i=next(i for i,x in enumerate(lines) if x.startswith("Ticker,Name,"))
df=pd.read_csv(io.StringIO("\n".join(lines[i:])))
if "Asset Class" in df.columns:
    df=df[df["Asset Class"].astype(str).str.lower().eq("equity")]
c=save("russell2000.txt",df["Ticker"],"# Current IWM equity holdings; practical Russell 2000 scanner proxy")

allv=sorted(set(a)|set(b)|set(c)|{"SPY","QQQ"})
(DATA/"all_unique.txt").write_text("# Combined unique universe\n"+"\n".join(allv)+"\n",encoding="utf-8")
print("S&P 500:",len(a))
print("Nasdaq-100:",len(b))
print("Russell/IWM proxy:",len(c))
print("Combined:",len(allv))
