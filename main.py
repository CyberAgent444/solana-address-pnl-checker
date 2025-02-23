import os
import requests
import json
import threading
import webbrowser
from flask import Flask, request, redirect, url_for, send_from_directory

API_KEY = ""
TX_LIMIT = 100
ENDPOINT_TEMPLATE = "https://api.helius.xyz/v0/addresses/{address}/transactions?api-key={api_key}&limit={limit}"

def get_transactions(wallet_address, limit=TX_LIMIT):
    url = ENDPOINT_TEMPLATE.format(address=wallet_address, api_key=API_KEY, limit=limit)
    response = requests.get(url)
    if response.status_code != 200:
        return []
    try:
        transactions = response.json()
    except Exception:
        return []
    return transactions

def update_pnl(pnl_data, token, amount, is_sale):
    if token not in pnl_data:
        pnl_data[token] = {"total_bought": 0.0, "total_sold": 0.0, "net_pnl": 0.0}
    if is_sale:
        pnl_data[token]["total_sold"] += amount
        pnl_data[token]["net_pnl"] += amount
    else:
        pnl_data[token]["total_bought"] += amount
        pnl_data[token]["net_pnl"] -= amount

def process_transactions(transactions):
    pnl_data = {}
    for tx in transactions:
        block_time = tx.get("blockTime", 0)
        events = tx.get("events", {})
        swap_event = events.get("swap")
        if swap_event:
            if swap_event.get("nativeInput"):
                try:
                    sol_spent = float(swap_event["nativeInput"].get("amount", 0)) / 1e9
                except Exception:
                    sol_spent = 0.0
                token = swap_event.get("tokenOutputs", [{}])[0].get("mint", "UNKNOWN")
                update_pnl(pnl_data, token, sol_spent, is_sale=False)
                if "latest_trade" not in pnl_data[token]:
                    pnl_data[token]["latest_trade"] = block_time
                    pnl_data[token]["earliest_trade"] = block_time
                else:
                    pnl_data[token]["latest_trade"] = max(pnl_data[token]["latest_trade"], block_time)
                    pnl_data[token]["earliest_trade"] = min(pnl_data[token]["earliest_trade"], block_time)
            if swap_event.get("nativeOutput"):
                try:
                    sol_received = float(swap_event["nativeOutput"].get("amount", 0)) / 1e9
                except Exception:
                    sol_received = 0.0
                token = swap_event.get("tokenInputs", [{}])[0].get("mint", "UNKNOWN")
                update_pnl(pnl_data, token, sol_received, is_sale=True)
                if "latest_trade" not in pnl_data[token]:
                    pnl_data[token]["latest_trade"] = block_time
                    pnl_data[token]["earliest_trade"] = block_time
                else:
                    pnl_data[token]["latest_trade"] = max(pnl_data[token]["latest_trade"], block_time)
                    pnl_data[token]["earliest_trade"] = min(pnl_data[token]["earliest_trade"], block_time)
    return pnl_data

def generate_report(wallet_address, pnl_data):
    output_dir = "Output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    filename = os.path.join(output_dir, f"{wallet_address}.html")
    sorted_tokens = sorted(pnl_data.items(), key=lambda x: x[1].get("latest_trade", 0), reverse=True)
    total_tokens = len(sorted_tokens)
    winning_tokens_count = sum(1 for token, data in sorted_tokens if data["net_pnl"] > 0)
    win_rate = round((winning_tokens_count / total_tokens) * 100, 2) if total_tokens > 0 else 0
    rois = []
    buy_amounts = []
    for token, data in sorted_tokens:
        if data["total_bought"] > 0:
            roi = (data["net_pnl"] / data["total_bought"]) * 100
            rois.append(roi)
            buy_amounts.append(data["total_bought"])
    avg_roi = round(sum(rois) / len(rois), 2) if rois else "N/A"
    avg_buy = round(sum(buy_amounts) / len(buy_amounts), 2) if buy_amounts else "N/A"
    total_pnl = round(sum(data["net_pnl"] for token, data in sorted_tokens), 2)
    total_pnl_usd = round(total_pnl * 200, 2)
    token_cards = ""
    if not sorted_tokens:
        token_cards = "<p style='grid-column: 1 / -1; text-align: center;'>No swap transactions found.</p>"
    else:
        for i, (token, data) in enumerate(sorted_tokens):
            total_bought = round(data["total_bought"], 2)
            total_sold = round(data["total_sold"], 2)
            net_sol = round(data["net_pnl"], 2)
            net_usd = round(net_sol * 200, 2)
            roi_str = f"{round((data['net_pnl'] / data['total_bought']) * 100, 2)}%" if total_bought > 0 else "N/A"
            pnl_color = "#2AE3FF" if net_sol > 0 else "#AD2AFF" if net_sol < 0 else "#e0e0e0"
            latest_trade = data.get("latest_trade", 0)
            earliest_trade = data.get("earliest_trade", 0)
            token_cards += f"""
      <div class="token-card" data-order="{i}" data-latest="{latest_trade}" data-earliest="{earliest_trade}" onclick="openDexscreener('{token}', '{wallet_address}')">
        <h2>Token: <span>{token}</span></h2>
        <div class="detail">
          <p>Total Bought: {total_bought} SOL</p>
          <p>Total Sold: {total_sold} SOL</p>
          <p>Net PNL: <span style="color: {pnl_color};">{net_sol} SOL</span></p>
          <p>Approximate Value: <span style="color: {pnl_color};">{net_usd}$</span></p>
          <p>ROI: {roi_str}</p>
        </div>
      </div>
            """
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PNL Report for Wallet: {wallet_address}</title>
  <style>
    body {{
      background-color: #121212;
      color: #e0e0e0;
      font-family: 'Roboto', sans-serif;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding-top: 20px;
      overflow-x: hidden;
    }}
    .container {{
      width: 90%;
      max-width: 1200px;
      padding: 20px;
      background-color: #1e1e1e;
      border-radius: 15px;
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5);
      position: relative;
      overflow: hidden;
    }}
    h1 {{
      text-align: center;
      color: #ff69b4;
      margin-bottom: 10px;
      font-size: 2.5em;
      animation: glow 1.5s ease-in-out infinite alternate;
    }}
    @keyframes glow {{
      from {{
        text-shadow: 0 0 10px #ff69b4, 0 0 20px #ff69b4, 0 0 30px #ff69b4;
      }}
      to {{
        text-shadow: 0 0 20px #ff69b4, 0 0 40px #ff69b4, 0 0 60px #ff69b4;
      }}
    }}
    .wallet-address {{
      text-align: center;
      font-size: 1.8em;
      color: #c0c0c0;
      margin-bottom: 20px;
      word-break: break-all;
    }}
    .overall-stats {{
      display: flex;
      justify-content: space-around;
      flex-wrap: wrap;
      gap: 20px;
      margin-bottom: 30px;
    }}
    .stat-card {{
      background-color: #2a2a2a;
      padding: 20px;
      border-radius: 10px;
      text-align: center;
      flex: 1;
      min-width: 200px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
      transition: box-shadow 0.3s ease;
    }}
    .stat-card:hover {{
      box-shadow: 0 4px 8px rgba(255, 105, 180, 0.5);
    }}
    .stat-card p {{
      margin: 10px 0;
      font-size: 1.2em;
    }}
    .token-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 60px;
      padding: 40px;
    }}
    .token-card {{
      background-color: #303030;
      padding: 20px;
      border-radius: 10px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
      overflow: hidden;
      position: relative;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
      cursor: pointer;
    }}
    .token-card:hover {{
      transform: translateY(-5px);
      box-shadow: 0 4px 8px rgba(255, 105, 180, 0.4);
    }}
    .token-card h2 {{
      font-size: 1.2em;
      color: #ff69b4;
      margin-bottom: 10px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .detail p {{
      margin: 5px 0;
      font-size: 1.1em;
    }}
    .detail span {{
      font-weight: bold;
    }}
    .sakura {{
      position: absolute;
      width: 100%;
      height: 100%;
      overflow: hidden;
      pointer-events: none;
    }}
    .sakura span {{
      position: absolute;
      bottom: -100px;
      opacity: 0;
      width: 20px;
      height: 20px;
      background: #ff69b4;
      border-radius: 50%;
      animation: fall 5s linear infinite, fade 5s linear infinite;
    }}
    @keyframes fall {{
      0% {{
        transform: translateY(0) rotate(0deg);
      }}
      100% {{
        transform: translateY(600px) rotate(360deg);
      }}
    }}
    @keyframes fade {{
      0%, 20%, 100% {{
        opacity: 0;
      }}
      50% {{
        opacity: 1;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="sakura">
      <span style="left: 10%; animation-delay: 0s; animation-duration: 5s;"></span>
      <span style="left: 20%; animation-delay: 1s; animation-duration: 6s;"></span>
      <span style="left: 30%; animation-delay: 2s; animation-duration: 7s;"></span>
      <span style="left: 40%; animation-delay: 3s; animation-duration: 8s;"></span>
      <span style="left: 50%; animation-delay: 4s; animation-duration: 9s;"></span>
      <span style="left: 60%; animation-delay: 5s; animation-duration: 10s;"></span>
      <span style="left: 70%; animation-delay: 6s; animation-duration: 11s;"></span>
      <span style="left: 80%; animation-delay: 7s; animation-duration: 12s;"></span>
      <span style="left: 90%; animation-delay: 8s; animation-duration: 13s;"></span>
    </div>
    <h1>PNL Report for Wallet</h1>
    <div class="wallet-address">{wallet_address}</div>
    <div class="overall-stats">
      <div class="stat-card">
        <p><strong>Win Rate</strong></p>
        <p>{win_rate}%</p>
      </div>
      <div class="stat-card">
        <p><strong>Average ROI</strong></p>
        <p>{avg_roi}%</p>
      </div>
      <div class="stat-card">
        <p><strong>Average Buy Amount </strong></p>
        <p>{avg_buy} SOL</p>
      </div>
      <div class="stat-card">
        <p title="Approximate Value: {total_pnl_usd}$"><strong>Total PNL</strong></p>
        <p>{total_pnl} SOL</p>
      </div>
    </div>
    <div class="token-grid">
      {token_cards}
    </div>
  </div>
  <script>
    function openDexscreener(token, wallet) {{
      var url = "https://dexscreener.com/solana/" + token + "?maker=" + wallet;
      window.open(url, '_blank');
    }}
  </script>
</body>
</html>
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Report generated: {filename}")
    return filename

app = Flask(__name__)

@app.route('/')
def index():
    html_form = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Solana Report Generator</title>
  <style>
    body {
      background-color: #121212;
      color: #e0e0e0;
      font-family: 'Roboto', sans-serif;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      overflow-x: hidden;
    }
    .container {
      width: 90%;
      max-width: 560px;
      padding: 20px;
      background-color: #1e1e1e;
      border-radius: 15px;
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5);
      position: relative;
      overflow: hidden;
      text-align: center;
    }
    h1 {
      color: #ff69b4;
      margin-bottom: 20px;
      font-size: 2.5em;
      animation: glow 1.5s ease-in-out infinite alternate;
    }
    @keyframes glow {
      from {
        text-shadow: 0 0 10px #ff69b4, 0 0 20px #ff69b4, 0 0 30px #ff69b4;
      }
      to {
        text-shadow: 0 0 20px #ff69b4, 0 0 40px #ff69b4, 0 0 60px #ff69b4;
      }
    }
    input[type="text"] {
      width: 80%;
      padding: 10px;
      margin: 10px 0;
      border: none;
      border-radius: 4px;
      background-color: #2a2a2a;
      color: #e0e0e0;
    }
    input[type="submit"] {
      padding: 10px 20px;
      background-color: #ff69b4;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      transition: background-color 0.5s ease, color 0.5s ease;
    }
    input[type="submit"]:hover {
      background-color: white;
      color: #ff69b4;
    }
    .sakura {
      position: absolute;
      width: 100%;
      height: 100%;
      overflow: hidden;
      pointer-events: none;
    }
    .sakura span {
      position: absolute;
      bottom: -100px;
      opacity: 0;
      width: 20px;
      height: 20px;
      background: #ff69b4;
      border-radius: 50%;
      animation: fall 5s linear infinite, fade 5s linear infinite;
    }
    @keyframes fall {
      0% {
        transform: translateY(0) rotate(0deg);
      }
      100% {
        transform: translateY(600px) rotate(360deg);
      }
    }
    @keyframes fade {
      0%, 20%, 100% {
        opacity: 0;
      }
      50% {
        opacity: 1;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="sakura">
      <span style="left: 10%; animation-delay: 0s; animation-duration: 5s;"></span>
      <span style="left: 20%; animation-delay: 1s; animation-duration: 6s;"></span>
      <span style="left: 30%; animation-delay: 2s; animation-duration: 7s;"></span>
      <span style="left: 40%; animation-delay: 3s; animation-duration: 8s;"></span>
      <span style="left: 50%; animation-delay: 4s; animation-duration: 9s;"></span>
      <span style="left: 60%; animation-delay: 5s; animation-duration: 10s;"></span>
      <span style="left: 70%; animation-delay: 6s; animation-duration: 11s;"></span>
      <span style="left: 80%; animation-delay: 7s; animation-duration: 12s;"></span>
      <span style="left: 90%; animation-delay: 8s; animation-duration: 13s;"></span>
    </div>
    <h1>Solana Report Generator</h1>
    <form action="/run" method="post">
      <label for="wallet">Enter Solana wallet address:</label>
      <input type="text" id="wallet" name="wallet" required>
      <input type="submit" value="Generate Report">
    </form>
  </div>
</body>
</html>
"""
    return html_form

@app.route('/run', methods=['POST'])
def run_script():
    wallet_address = request.form.get("wallet")
    transactions = get_transactions(wallet_address)
    pnl_data = process_transactions(transactions)
    generate_report(wallet_address, pnl_data)
    return redirect(url_for('report_page', wallet=wallet_address))

@app.route('/report/<wallet>')
def report_page(wallet):
    report_link = url_for('serve_report', wallet=wallet)
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Report for {wallet}</title>
      <style>
        body {{
          background-color: #121212;
          color: #e0e0e0;
          font-family: 'Roboto', sans-serif;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
          overflow-x: hidden;
        }}
        .container {{
          width: 90%;
          max-width: 600px;
          padding: 20px;
          background-color: #1e1e1e;
          border-radius: 15px;
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5);
          position: relative;
          overflow: hidden;
          text-align: center;
        }}
        h1 {{
          color: #ff69b4;
          margin-bottom: 20px;
          font-size: 2.5em;
          animation: glow 1.5s ease-in-out infinite alternate;
        }}
        @keyframes glow {{
          from {{
            text-shadow: 0 0 10px #ff69b4, 0 0 20px #ff69b4, 0 0 30px #ff69b4;
          }}
          to {{
            text-shadow: 0 0 20px #ff69b4, 0 0 40px #ff69b4, 0 0 60px #ff69b4;
          }}
        }}
        a {{
          display: inline-block;
          padding: 10px 20px;
          margin-top: 20px;
          background-color: #ff69b4;
          color: white;
          text-decoration: none;
          border-radius: 4px;
          transition: background-color 0.5s ease, color 0.5s ease;
        }}
        a:hover {{
          background-color: white;
          color: #ff69b4;
        }}
        .sakura {{
          position: absolute;
          width: 100%;
          height: 100%;
          overflow: hidden;
          pointer-events: none;
        }}
        .sakura span {{
          position: absolute;
          bottom: -100px;
          opacity: 0;
          width: 20px;
          height: 20px;
          background: #ff69b4;
          border-radius: 50%;
          animation: fall 5s linear infinite, fade 5s linear infinite;
        }}
        @keyframes fall {{
          0% {{
            transform: translateY(0) rotate(0deg);
          }}
          100% {{
            transform: translateY(600px) rotate(360deg);
          }}
        }}
        @keyframes fade {{
          0%, 20%, 100% {{
            opacity: 0;
          }}
          50% {{
            opacity: 1;
          }}
        }}
        .wallet-address {{
          word-break: break-all;
          margin-bottom: 20px;
          font-size: 1.2em;
          padding: 10px;
          background-color: #2a2a2a;
          border-radius: 4px;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="sakura">
          <span style="left: 10%; animation-delay: 0s; animation-duration: 5s;"></span>
          <span style="left: 20%; animation-delay: 1s; animation-duration: 6s;"></span>
          <span style="left: 30%; animation-delay: 2s; animation-duration: 7s;"></span>
          <span style="left: 40%; animation-delay: 3s; animation-duration: 8s;"></span>
          <span style="left: 50%; animation-delay: 4s; animation-duration: 9s;"></span>
          <span style="left: 60%; animation-delay: 5s; animation-duration: 10s;"></span>
          <span style="left: 70%; animation-delay: 6s; animation-duration: 11s;"></span>
          <span style="left: 80%; animation-delay: 7s; animation-duration: 12s;"></span>
          <span style="left: 90%; animation-delay: 8s; animation-duration: 13s;"></span>
        </div>
        <h1>Report for</h1>
        <div class="wallet-address">{wallet}</div>
        <a href="{report_link}" target="_blank">Open Report in New Tab</a>
        <br>
        <a href="/">Return to Main Page</a>
      </div>
    </body>
    </html>
    """
    return html_content

@app.route('/serve_report/<wallet>')
def serve_report(wallet):
    output_dir = os.path.join(os.getcwd(), "Output")
    filename = f"{wallet}.html"
    return send_from_directory(output_dir, filename)

def open_browser():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    threading.Timer(1.25, open_browser).start()
    app.run(debug=False)
