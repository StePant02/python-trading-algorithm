import json
import time
import os
import sys
import shutil
from datetime import datetime
from colorama import init

init(autoreset=True)

# ==========================================
# ΡΥΘΜΙΣΕΙΣ V6 - MASTER EXECUTOR
# ==========================================
# ΕΠΙΛΟΓΕΣ: "CONSERVATIVE" | "AGGRESSIVE" | "UNLEASHED"
EXECUTION_MODE = "CONSERVATIVE" 

TRADE_SIZE = 15.0
FEE_RATE = 0.0007              
STOP_LOSS_PCT = 0.005         
TIME_STOP_MINUTES = 15        

PARTIAL_TP_PCT = 0.007        
RUNNER_FLOOR = 0.004          
RUNNER_TRAIL_DIST = 0.006     

COOLDOWN_MINUTES = 10         # 10 λεπτά καραντίνα μετά από SL

# Δυναμική προσαρμογή βάσει του MODE
if EXECUTION_MODE == "UNLEASHED":
    MAX_TRADES = 10
    ALLOW_HIJACK = False
elif EXECUTION_MODE == "AGGRESSIVE":
    MAX_TRADES = 3
    ALLOW_HIJACK = True
else: # CONSERVATIVE
    MAX_TRADES = 3
    ALLOW_HIJACK = False

def get_signal_data(filepath="signal.json"):
    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f: return json.load(f)
    except: pass
    return None

def log_event(message, session_file):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(f"\n{log_msg}")
    with open(session_file, "a", encoding="utf-8") as f:
        clean_msg = log_msg.replace('\033[96m', '').replace('\033[0m', '').replace('\033[93m', '')
        f.write(clean_msg + "\n")

def main():
    current_folder = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_folder, "signal.json")
    session_file = os.path.join(current_folder, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    os.system('cls' if os.name == 'nt' else 'clear')
    log_event(f"🚀 V6 Executor | Mode: {EXECUTION_MODE} | Max Trades: {MAX_TRADES} | Cooldown: {COOLDOWN_MINUTES}m", session_file)
    
    active_trades = {}
    cooldown_list = {} # {'BTCUSDT': timestamp_που_εφαγε_SL}
    
    stats = {
        "trades_opened": 0, "partial_tps": 0, "stop_losses": 0,
        "time_stops": 0, "runner_floor_exits": 0, "runner_trail_exits": 0, 
        "hijacked_trades": 0, "gross_pnl_usd": 0.0, "fees_paid_usd": 0.0, "net_pnl_usd": 0.0
    }

    try:
        while True:
            data = get_signal_data(json_path)
            if not data:
                time.sleep(1)
                continue
                
            latest_prices = data.get("prices", {})
            signals = data.get("signals", {})
            status_parts = [] 
            
            # 1. ΔΙΑΧΕΙΡΙΣΗ ΑΝΟΙΧΤΩΝ ΘΕΣΕΩΝ
            for symbol, trade in list(active_trades.items()):
                current_price = latest_prices.get(symbol)
                if not current_price: continue
                
                entry = trade['entry_price']
                side = trade['side']
                
                gross_pnl = (current_price - entry) / entry if side == "LONG" else (entry - current_price) / entry
                net_pnl = gross_pnl - FEE_RATE
                trade['current_net_pnl'] = net_pnl
                
                elapsed_minutes = (time.time() - trade['start_time']) / 60
                
                if not trade['is_runner']:
                    if net_pnl >= PARTIAL_TP_PCT:
                        size = TRADE_SIZE * 0.9
                        stats["gross_pnl_usd"] += size * gross_pnl; stats["fees_paid_usd"] += size * FEE_RATE; stats["net_pnl_usd"] += size * net_pnl
                        log_event(f"🟢 PARTIAL TP: {symbol} | Gross: {gross_pnl*100:+.2f}% | Net: {net_pnl*100:+.2f}%", session_file)
                        trade['is_runner'] = True
                        trade['highest_net_pnl'] = net_pnl 
                        stats["partial_tps"] += 1
                        
                    elif net_pnl <= -STOP_LOSS_PCT:
                        size = TRADE_SIZE
                        stats["gross_pnl_usd"] += size * gross_pnl; stats["fees_paid_usd"] += size * FEE_RATE; stats["net_pnl_usd"] += size * net_pnl
                        log_event(f"🔴 STOP LOSS: {symbol} | Gross: {gross_pnl*100:+.2f}% | Net: {net_pnl*100:+.2f}%", session_file)
                        del active_trades[symbol]
                        cooldown_list[symbol] = time.time() # Βάλε καραντίνα
                        stats["stop_losses"] += 1
                        
                    elif elapsed_minutes >= TIME_STOP_MINUTES:
                        size = TRADE_SIZE
                        stats["gross_pnl_usd"] += size * gross_pnl; stats["fees_paid_usd"] += size * FEE_RATE; stats["net_pnl_usd"] += size * net_pnl
                        st = "🟢" if net_pnl > 0 else "🔴"
                        log_event(f"⏱️ TIME STOP (15m): {symbol} | {st} Gross: {gross_pnl*100:+.2f}% | Net: {net_pnl*100:+.2f}%", session_file)
                        del active_trades[symbol]
                        # Αν έκλεισε με ζημιά, βάλε καραντίνα
                        if net_pnl < 0: cooldown_list[symbol] = time.time()
                        stats["time_stops"] += 1
                        
                    status_parts.append(f"[MAIN {symbol}: Net {net_pnl*100:+.2f}%]")
                
                else:
                    if net_pnl > trade.get('highest_net_pnl', 0): trade['highest_net_pnl'] = net_pnl
                    current_stop = max(RUNNER_FLOOR, trade['highest_net_pnl'] - RUNNER_TRAIL_DIST)
                    
                    if net_pnl <= current_stop:
                        size = TRADE_SIZE * 0.1
                        stats["gross_pnl_usd"] += size * gross_pnl; stats["fees_paid_usd"] += size * FEE_RATE; stats["net_pnl_usd"] += size * net_pnl
                        if current_stop == RUNNER_FLOOR:
                            log_event(f"🛡️ ANCHOR EXIT: {symbol} | Gross: {gross_pnl*100:+.2f}% | Net: {net_pnl*100:+.2f}%", session_file)
                            stats["runner_floor_exits"] += 1
                        else:
                            log_event(f"🚀 TRAILING EXIT: {symbol} | Gross: {gross_pnl*100:+.2f}% | Net: {net_pnl*100:+.2f}%", session_file)
                            stats["runner_trail_exits"] += 1
                        del active_trades[symbol]
                        
                    status_parts.append(f"[\033[96mRUNNER {symbol}: Net {net_pnl*100:+.2f}%\033[0m]")

            # 2. ΝΕΕΣ ΕΙΣΟΔΟΙ & HIJACK LOGIC
            for symbol, sig_data in signals.items():
                if symbol in active_trades: continue
                
                # Check JSON Format (Smart vs Old)
                if isinstance(sig_data, dict):
                    sig, strength = sig_data.get("side", "NONE"), sig_data.get("strength", "NONE")
                else:
                    sig, strength = sig_data, "NONE"
                    
                if sig not in ["LONG", "SHORT"]: continue
                
                # Check Cooldown
                if symbol in cooldown_list:
                    if (time.time() - cooldown_list[symbol]) < (COOLDOWN_MINUTES * 60):
                        continue # Αγνόησε το σήμα, είναι σε καραντίνα
                    else:
                        del cooldown_list[symbol] # Έληξε η καραντίνα
                
                price = latest_prices.get(symbol)
                if not price: continue
                
                # Αν υπάρχει χώρος (κάτω από Max Trades)
                if len(active_trades) < MAX_TRADES:
                    log_event(f"⚡ ΝΕΑ ΕΙΣΟΔΟΣ: {sig} στο {symbol} ({strength}) | Τιμή: {price:.4f}", session_file)
                    active_trades[symbol] = {'side': sig, 'entry_price': price, 'start_time': time.time(), 'is_runner': False, 'highest_net_pnl': 0.0, 'current_net_pnl': 0.0}
                    stats["trades_opened"] += 1
                    
                # Αν δεν υπάρχει χώρος, αλλά επιτρέπεται Hijack και έχουμε GOLDEN σήμα
                elif ALLOW_HIJACK and strength == "GOLDEN":
                    worst_symbol = None
                    worst_pnl = 0
                    
                    # Ψάξε το χειρότερο MAIN trade που χάνει χρήματα
                    for act_sym, trade in active_trades.items():
                        if not trade['is_runner'] and trade['current_net_pnl'] < worst_pnl:
                            worst_pnl = trade['current_net_pnl']
                            worst_symbol = act_sym
                            
                    if worst_symbol:
                        # Σκότωσε το κακό trade
                        trade_to_kill = active_trades[worst_symbol]
                        size = TRADE_SIZE
                        gross_pnl_k = trade_to_kill['current_net_pnl'] + FEE_RATE
                        stats["gross_pnl_usd"] += size * gross_pnl_k; stats["fees_paid_usd"] += size * FEE_RATE; stats["net_pnl_usd"] += size * worst_pnl
                        log_event(f"\033[93m🗡️ HIJACK: Κλείσιμο {worst_symbol} (Net: {worst_pnl*100:+.2f}%) για να μπει το GOLDEN {symbol}\033[0m", session_file)
                        del active_trades[worst_symbol]
                        stats["hijacked_trades"] += 1
                        
                        # Άνοιξε το νέο
                        log_event(f"⚡ ΝΕΑ ΕΙΣΟΔΟΣ: {sig} στο {symbol} (GOLDEN HIJACK) | Τιμή: {price:.4f}", session_file)
                        active_trades[symbol] = {'side': sig, 'entry_price': price, 'start_time': time.time(), 'is_runner': False, 'highest_net_pnl': 0.0, 'current_net_pnl': 0.0}
                        stats["trades_opened"] += 1

            # 3. UI ΕΚΤΥΠΩΣΗ
            status_text = " | ".join(status_parts).replace('\033[96m', '').replace('\033[0m', '') if status_parts else f"Αναμονή ({len(active_trades)}/{MAX_TRADES} Ανοιχτά)..."
            term_width = getattr(shutil.get_terminal_size(), 'columns', 100) - 2
            if len(status_text) > term_width: status_text = status_text[:term_width-3] + "..."
            else: status_text = status_text.ljust(term_width)
                
            sys.stdout.write(f"\r{status_text}")
            sys.stdout.flush()
            time.sleep(1)

    except KeyboardInterrupt:
        sys.stdout.write("\n\n") 
        log_event("⚠️ ΕΝΤΟΛΗ ΤΕΡΜΑΤΙΣΜΟΥ (Ctrl+C). Ασφαλής Έξοδος...", session_file)
        
        if active_trades:
            for symbol, trade in active_trades.items():
                curr_price = latest_prices.get(symbol, trade['entry_price'])
                gross_pnl = (curr_price - trade['entry_price']) / trade['entry_price'] if trade['side'] == "LONG" else (trade['entry_price'] - curr_price) / trade['entry_price']
                net_pnl = gross_pnl - FEE_RATE
                
                size_factor = 0.1 if trade['is_runner'] else 1.0
                size = TRADE_SIZE * size_factor
                stats["gross_pnl_usd"] += size * gross_pnl; stats["fees_paid_usd"] += size * FEE_RATE; stats["net_pnl_usd"] += size * net_pnl
                
                t_type = "RUNNER (10%)" if trade['is_runner'] else "MAIN (100%)"
                st = "🟢" if net_pnl > 0 else "🔴"
                log_event(f"🛑 ΑΝΑΓΚΑΣΤΙΚΟ ΚΛΕΙΣΙΜΟ: {symbol} [{t_type}] | {st} Gross: {gross_pnl*100:+.2f}% | Net: {net_pnl*100:+.2f}%", session_file)
        else:
            log_event("✅ Κανένα ανοιχτό trade. Ασφαλής τερματισμός.", session_file)
            
        summary = f"""
======================================
📊 ΣΥΝΟΨΗ SESSION ({EXECUTION_MODE})
======================================
Συνολικά Trades Που Άνοιξαν   : {stats['trades_opened']}
Trades Που Έγιναν Hijack      : {stats['hijacked_trades']}
--------------------------------------
💰 ΟΙΚΟΝΟΜΙΚΟΣ ΑΠΟΛΟΓΙΣΜΟΣ
Μεικτό Κέρδος Αγοράς (Gross)  : ${stats['gross_pnl_usd']:.2f}
Εκτιμώμενες Προμήθειες (Fees) : -${stats['fees_paid_usd']:.2f}
ΤΕΛΙΚΟ ΚΑΘΑΡΟ ΚΕΡΔΟΣ (Net)    : ${stats['net_pnl_usd']:.2f}
--------------------------------------
[MAIN TRADES (90%)]
🟢 Partial TPs (+0.7% Net)    : {stats['partial_tps']}
🔴 Stop Losses (-0.5% Net)    : {stats['stop_losses']}
⏱️ Time Stops (15 λεπτά)        : {stats['time_stops']}
--------------------------------------
[RUNNERS (10%)]
🚀 Trailing Exits (High PnL)  : {stats['runner_trail_exits']}
🛡️ Anchor Floor Exits (+0.4%) : {stats['runner_floor_exits']}
======================================
"""
        print(summary)
        with open(session_file, "a", encoding="utf-8") as f: f.write(summary)
        sys.exit(0)

if __name__ == "__main__":
    main()