import requests
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

TELEGRAM_BOT_TOKEN = "8849551920:AAGZ2vYs6tO9af4AP9JTIs7FBm_zn3Ft2Xo"
TELEGRAM_CHAT_ID   = "7650727007"

G1_EXIT_PCT    = -0.03
G1_REENTER_PCT = -0.015
G2_EXIT_VOL    =  0.36
G2_CLEAR_VOL   =  0.25
G3_EXIT_VR     =  1.40
G3_CLEAR_VR    =  1.10
G4_EXIT_CREDIT = -0.04
G5_WARN_PCT    =  0.30
G5_HARD_PCT    =  0.40

def fetch(ticker, days=260):
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                     end=end.strftime("%Y-%m-%d"),
                     progress=False, auto_adjust=True,
                     multi_level_index=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    return df["Close"].squeeze().dropna()

def gate1(spy):
    sma200 = spy.rolling(200).mean().iloc[-1]
    pct    = (spy.iloc[-1] - sma200) / sma200
    if pct <= G1_EXIT_PCT:
        return False, f"🔴 G1 FAIL — SPY {pct:.2%} below 200-SMA"
    if pct <= G1_REENTER_PCT:
        return False, f"🟡 G1 WARN — SPY {pct:.2%} below 200-SMA"
    return True, f"🟢 G1 OK — SPY {pct:.2%} above 200-SMA"

def gate2(qqq):
    rets  = np.log(qqq / qqq.shift(1)).dropna()
    vol15 = rets.iloc[-15:].std() * np.sqrt(252)
    if vol15 > G2_EXIT_VOL:
        return False, f"🔴 G2 FAIL — QQQ vol {vol15:.1%} (exit >{G2_EXIT_VOL:.0%})"
    if vol15 > G2_CLEAR_VOL:
        return False, f"🟡 G2 WARN — QQQ vol {vol15:.1%}"
    return True, f"🟢 G2 OK — QQQ vol {vol15:.1%}"

def gate3(qqq):
    rets  = np.log(qqq / qqq.shift(1)).dropna()
    vol5  = rets.iloc[-5:].std()  * np.sqrt(252)
    vol20 = rets.iloc[-20:].std() * np.sqrt(252)
    vr    = vol5 / vol20 if vol20 > 0 else 0
    if vr > G3_EXIT_VR:
        return False, f"🔴 G3 FAIL — Vol-ratio {vr:.2f} (exit >{G3_EXIT_VR})"
    if vr > G3_CLEAR_VR:
        return False, f"🟡 G3 WARN — Vol-ratio {vr:.2f}"
    return True, f"🟢 G3 OK — Vol-ratio {vr:.2f}"

def gate4(hyg, lqd):
    ratio = hyg / lqd
    roc20 = (ratio.iloc[-1] - ratio.iloc[-21]) / ratio.iloc[-21]
    if roc20 < G4_EXIT_CREDIT:
        return False, f"🔴 G4 FAIL — Credit ROC {roc20:.2%} (exit <{G4_EXIT_CREDIT:.0%})"
    return True, f"🟢 G4 OK — Credit ROC {roc20:.2%}"

def gate5(qqq):
    sma200 = qqq.rolling(200).mean().iloc[-1]
    pct    = (qqq.iloc[-1] - sma200) / sma200
    if pct >= G5_HARD_PCT:
        return False, f"🔴 G5 HARD EXIT — QQQ {pct:.2%} above 200-SMA"
    if pct >= G5_WARN_PCT:
        return True,  f"🟡 G5 WARN — QQQ {pct:.2%} above 200-SMA"
    return True, f"🟢 G5 OK — QQQ {pct:.2%} above 200-SMA"

def send(msg):
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=10)

def run():
    print("Fetching data...")
    spy = fetch("SPY")
    qqq = fetch("QQQ")
    hyg = fetch("HYG", days=40)
    lqd = fetch("LQD", days=40)

    g1_ok, g1_msg = gate1(spy)
    g2_ok, g2_msg = gate2(qqq)
    g3_ok, g3_msg = gate3(qqq)
    g4_ok, g4_msg = gate4(hyg, lqd)
    g5_ok, g5_msg = gate5(qqq)

    all_clear = g1_ok and g2_ok and g3_ok and g4_ok and g5_ok

    if all_clear:
        signal = "🟢 *RISK-ON — HOLD / BUY TQQQ*"
        action = "✅ No action needed — stay in TQQQ"
    else:
        signal = "🔴 *RISK-OFF — EXIT TO CASH (SGOV)*"
        action = "⚠️ *ACTION REQUIRED — Sell TQQQ on Webull*"

    msg = f"""
*Sentinel Daily Update*
`{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`

{signal}
{action}

*Gate Status:*
{g1_msg}
{g2_msg}
{g3_msg}
{g4_msg}
{g5_msg}
    """.strip()

    send(msg)
    print("Telegram message sent.")
    print(msg)

if __name__ == "__main__":
    run()
