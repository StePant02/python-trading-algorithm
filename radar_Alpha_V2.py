import ccxt, time, os, json
import pandas as pd
import numpy as np
from colorama import init, Fore, Style

init(autoreset=True)
exchange = ccxt.binance()
LIMIT = 600 
MAJORS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']

BLACKLIST_BASES = ['USDC', 'FDUSD', 'TUSD', 'BUSD', 'USDE', 'DAI', 'USDD', 'EUR', 'USD1', 'AEUR']

YEL = Fore.YELLOW
CYA = Fore.CYAN
RES = Style.RESET_ALL
BR = Style.BRIGHT

def fmt_p(price):
    if price >= 1000: return f"{price:.1f}"
    elif price >=100: return f"{price:.2f}"
    elif price >= 10: return f"{price:.3f}"
    elif price >= 1: return f"{price:.4f}"
    else: return f"{price:.5f}"

def pine_rma_manual(series, length):
    alpha = 1 / length
    s_values = series.fillna(0).values
    rma_values = np.zeros_like(s_values)
    if len(s_values) > length:
        sma_start = np.mean(s_values[:length])
        rma_values[length-1] = sma_start
        for i in range(length, len(s_values)):
            rma_values[i] = alpha * s_values[i] + (1 - alpha) * rma_values[i-1]
    return pd.Series(rma_values, index=series.index)

def calculate_logic(df, n=14):
    df['up'], df['down'] = df['high'].diff(), -df['low'].diff()
    df['plusDM'] = np.where((df['up'] > df['down']) & (df['up'] > 0), df['up'], 0.0)
    df['minusDM'] = np.where((df['down'] > df['up']) & (df['down'] > 0), df['down'], 0.0)
    df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    tr_rma = pine_rma_manual(df['tr'], n)
    plus = (100 * pine_rma_manual(df['plusDM'], n) / tr_rma).ffill().fillna(0)
    minus = (100 * pine_rma_manual(df['minusDM'], n) / tr_rma).ffill().fillna(0)
    sum_di = plus + minus
    adx = 100 * pine_rma_manual(abs(plus - minus) / np.where(sum_di == 0, 1, sum_di), n)
    
    return {
        'adx': adx.iloc[-1], 'prev': adx.iloc[-2], 
        'p': plus.iloc[-1], 'm': minus.iloc[-1], 
        'ema20': df['close'].ewm(span=20, adjust=False).mean().iloc[-1], 
        'last': df['close'].iloc[-1], 'vol': df['vol']
    }

def process_symbol(symbol):
    try:
        bars_15m = exchange.fetch_ohlcv(symbol, '15m', limit=200)
        ema200_15m = pd.DataFrame(bars_15m, columns=['ts','o','h','l','c','v'])['c'].ewm(span=200, adjust=False).mean().iloc[-1]
        
        bars_1m = exchange.fetch_ohlcv(symbol, '1m', limit=LIMIT)
        df_1m = pd.DataFrame(bars_1m, columns=['ts','open','high','low','close','vol'])
        d1 = calculate_logic(df_1m)
        
        # --- SNIPER FILTERS (ΤΑ 3 ΑΠΟΛΥΤΑ ΚΡΙΤΗΡΙΑ) ---
        side = "BULL" if d1['p'] > d1['m'] else "BEAR"
        
        # 1. Volume Anomaly (Τουλάχιστον 2.5x πάνω από τον μέσο όρο 20 λεπτών)
        v_rat = d1['vol'].iloc[-1] / d1['vol'].tail(20).mean()
        pass_vol = v_rat >= 2.5
        
        # 2. Anti-Climax Ceiling (ADX μεταξύ 25 και 45, για αποφυγή αγοράς στην κορυφή)
        pass_adx = 25 <= d1['adx'] <= 45
        
        # 3. Pullback / Proximity (Απόσταση μικρότερη του 0.15% από τον EMA 20 του 1 λεπτού)
        dist_ema = abs(d1['last'] - d1['ema20']) / d1['last']
        pass_pullback = dist_ema <= 0.0015
        
        # 4. Βασική τάση 15 λεπτών (Αυτό υπήρχε ήδη και δούλευε)
        is_above_ema15m = d1['last'] > ema200_15m
        pass_trend = (side == "BULL" and is_above_ema15m) or (side == "BEAR" and not is_above_ema15m)

        # ΜΟΝΟ αν περνάνε ΚΑΙ ΤΑ 4 αυστηρά φίλτρα, δίνει σήμα
        sig = "SCAN"
        strength = "NONE"
        if pass_vol and pass_adx and pass_pullback and pass_trend:
            sig = f"GOLDEN {side} *"
            strength = "GOLDEN"
            
        return [
            symbol.replace('/USDT', ''), fmt_p(d1['last']),
            f"{d1['adx']:.1f}", f"{dist_ema*100:.2f}%", f"{v_rat:.1f}x",
            side, sig, strength, d1['last']
        ]
    except: return None

W = [10, 10, 8, 10, 8, 6, 15]
H = ['PAIR', 'PRICE', 'ADX', 'DIST_EMA', 'V-RAT', 'SIDE', 'SIGNAL']

def print_table(rows, title):
    if not rows: return
    header_line = " ".join([f"{H[i]:<{W[i]}}" for i in range(len(H))])
    print(f"\n{BR}{title}")
    print("=" * len(header_line))
    print(header_line)
    print("-" * len(header_line))
    for r in rows:
        color = YEL if "GOLDEN" in r[6] else RES
        line = f"{r[0]:<{W[0]}} {r[1]:>{W[1]}}  {r[2]:>{W[2]-1}}  {r[3]:>{W[3]-1}}  {r[4]:>{W[4]-1}}  {r[5]:<{W[5]}}  {color}{r[6]:<{W[6]}}{RES}"
        print(line)

def run_scanner():
    try:
        t = exchange.fetch_tickers()
        valid_pairs = [k for k, v in t.items() if '/USDT' in k and v['quoteVolume'] > 5e6 and k.split('/')[0] not in BLACKLIST_BASES]
        pairs = sorted(valid_pairs, key=lambda x: t[x]['quoteVolume'], reverse=True)[:25]
        
        results = [process_symbol(s) for s in pairs]
        results = [x for x in results if x is not None]
        
        # Εμφανίζουμε πάνω αυτούς που έχουν σήμα
        active_signals = [r for r in results if r[7] != "NONE"]
        scanning = [r for r in results if r[7] == "NONE"][:10]

        os.system('cls' if os.name == 'nt' else 'clear')
        print_table(active_signals, "BETAV1 SNIPER: ACTIVE TARGETS")
        print_table(scanning, "SCANNING (Awaiting perfect conditions)")
        
        market_data = {"prices": {}, "signals": {}}
        for r in results:
            symbol = r[0] + "USDT"       
            clean_price = float(r[8])                  
            signal_type = "LONG" if r[5] == "BULL" else "SHORT"
            
            market_data["prices"][symbol] = clean_price
            if r[7] != "NONE":
                market_data["signals"][symbol] = {"side": signal_type, "strength": r[7]}

        current_folder = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_folder, "signal.json")
        if market_data["prices"]: 
            with open(json_path, "w") as f:
                json.dump(market_data, f)
            
    except Exception as e: print(f"Error: {e}")

print("--- BETAV1 SNIPER (HYPERLIQUID READY) ---")
while True:
    run_scanner()
    time.sleep(15)