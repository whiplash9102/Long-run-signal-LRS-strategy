import pandas as pd
import numpy as np

def run_okx_simulation(prices_csv="data/processed/prices_adjusted.csv", 
                       signals_csv="data/processed/signals.csv",
                       leverages=[1.0, 1.25, 2.0, 3.0],
                       funding_rate_annual=0.10, # 10% annual borrow cost
                       slippage_bps=2.0 # 2 bps per side
                      ):
    prices = pd.read_csv(prices_csv, parse_dates=["date"])
    spy_prices = prices[prices["ticker"] == "SPY"].sort_values("date").reset_index(drop=True)
    
    signals = pd.read_csv(signals_csv, parse_dates=["date", "next_execution_date"])
    spy_signals = signals[(signals["ticker"] == "SPY") & (signals["filter_id"] == "SMA_200")].copy()
    spy_signals = spy_signals.sort_values("date").reset_index(drop=True)
    
    # We will build trades list
    # A trade opens when current_state flips to LONG (and signal_is_tradable)
    # A trade closes when current_state flips to RISK_OFF
    
    trades = []
    in_trade = False
    entry_date = None
    entry_price = None
    
    for _, row in spy_signals.iterrows():
        if not row["signal_is_tradable"]: continue
        
        state = row["current_state"]
        event = row["signal_event"]
        exec_date = row["next_execution_date"]
        
        # We need the open price of exec_date
        price_row = spy_prices[spy_prices["date"] == exec_date]
        if price_row.empty:
            continue
            
        exec_price = price_row.iloc[0]["adjusted_open"]
        
        if event == "BUY_ALERT" and not in_trade:
            in_trade = True
            entry_date = exec_date
            entry_price = exec_price
        elif event == "EXIT_ALERT" and in_trade:
            in_trade = False
            exit_date = exec_date
            exit_price = exec_price
            
            # Check the lowest point during the trade for liquidation
            trade_period = spy_prices[(spy_prices["date"] >= entry_date) & (spy_prices["date"] <= exit_date)]
            lowest_price = trade_period["adjusted_low"].min() if "adjusted_low" in trade_period.columns else trade_period["adjusted_close"].min()
            
            trades.append({
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "lowest_price": lowest_price,
                "hold_days": (exit_date - entry_date).days
            })
            
    print("==================================================================")
    print("🔥 OKX MARGIN SIMULATION: SPY LRS (SMA-200) 🔥")
    print(f"Funding Rate: {funding_rate_annual*100}%/năm | Trading Fee: {slippage_bps*2} bps (Round trip)")
    print("==================================================================\n")
    
    for lev in leverages:
        equity = 10000.0
        peak_equity = 10000.0
        max_dd = 0.0
        liquidated = False
        
        trade_returns = []
        
        for t in trades:
            if liquidated: break
            
            # 1. Check liquidation
            # If price drops to a point where: Leverage * (lowest_price / entry_price - 1) <= -1.0
            max_unrealized_drop = lev * (t["lowest_price"] / t["entry_price"] - 1.0)
            if max_unrealized_drop <= -0.95: # OKX usually liquidates before exactly -100%
                liquidated = True
                equity = 0
                max_dd = -1.0
                print(f"[!] BỊ THANH LÝ (CHÁY) ở mức đòn bẩy {lev}x vào ngày {t['exit_date'].date()}!")
                break
            
            # 2. Calculate PnL
            raw_return = (t["exit_price"] / t["entry_price"]) - 1.0
            gross_trade_return = lev * raw_return
            
            # 3. Fees
            borrowed_amount_ratio = lev - 1.0
            funding_fee = borrowed_amount_ratio * funding_rate_annual * (t["hold_days"] / 365.0)
            trading_fee = lev * (slippage_bps * 2 / 10000.0)
            
            net_trade_return = gross_trade_return - funding_fee - trading_fee
            
            trade_returns.append(net_trade_return)
            equity *= (1.0 + net_trade_return)
            
            if equity > peak_equity:
                peak_equity = equity
            else:
                dd = (equity / peak_equity) - 1.0
                if dd < max_dd:
                    max_dd = dd
        
        years = (trades[-1]["exit_date"] - trades[0]["entry_date"]).days / 365.25
        if liquidated:
            cagr = -1.0
        else:
            cagr = (equity / 10000.0) ** (1.0 / years) - 1.0
            
        print(f"🔹 Đòn bẩy {lev}x (Mô phỏng OKX):")
        print(f"   - Lợi nhuận gộp (CAGR): {cagr*100:.2f}% / năm")
        print(f"   - Max Drawdown:        {max_dd*100:.2f}%")
        print(f"   - Tiền cuối cùng:      ${equity:,.0f} (Từ $10,000)")
        print(f"   - Tổng số lệnh:        {len(trade_returns)} lệnh")
        print("-" * 65)

if __name__ == '__main__':
    run_okx_simulation()
