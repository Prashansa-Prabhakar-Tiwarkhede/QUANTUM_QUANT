import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib
from dotenv import load_dotenv  # <-- ADD THIS

load_dotenv()
matplotlib.use('Agg')  # ✅ disables GUI backend

def get_stock_data(stock):
    df = yf.download(stock, period="6mo")
    return df

def predict_stock(stock):
    df = get_stock_data(stock)

    # Safety check
    if df is None or df.empty or len(df) < 10:
        return None, None, "Not enough data"

    df = df[['Close']].copy()
    df['Days'] = np.arange(len(df))

    X = df[['Days']]
    y = df['Close']

    model = LinearRegression()
    model.fit(X, y)

    next_day = np.array([[len(df)]])

    current = float(df["Close"].tail(1).iloc[0])   # force scalar
    prediction = float(model.predict(next_day)[0])  # force scalar

    change = float(((prediction - current) / current) * 100)
    if change > 2:
        decision = "BUY"
    elif change < -2:
        decision = "SELL"
    else:
        decision = "HOLD"

    return round(current, 2), round(prediction, 2), decision

import matplotlib.pyplot as plt
import os

def generate_trend_graph(stock):
    df = get_stock_data(stock)
    
    if df is None or df.empty:
        return ""

    plt.figure(figsize=(8,5))
    # Draw a sleek blue line for the trend
    plt.plot(df['Close'], color='#3b82f6', linewidth=2)
    plt.title(f"{stock} 6-Month Price Trend", color='white')
    plt.xlabel("Days", color='gray')
    plt.ylabel("Price ($)", color='gray')
    
    # Make the graph background transparent to blend into your holographic UI
    plt.gca().set_facecolor('none')
    plt.gcf().patch.set_facecolor('none')
    plt.tick_params(colors='gray')

    filename = f"static/{stock}_trend.png"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    plt.savefig(filename)
    plt.close()

    return filename
def generate_comparison_graph(comparison_data, filename="static/stock_comparison.png"):
    stocks = []
    returns = []
    risks = []

    for d in comparison_data:
        stocks.append(d['stock'])
        
        rp = d.get('return_percent', 0)
        if isinstance(rp, (list, tuple, np.ndarray)):
            rp = rp[0] if len(rp) > 0 else 0.0
        try:
            returns.append(float(rp))
        except:
            returns.append(0.0)

        rk = d.get('risk', 0)
        if isinstance(rk, (list, tuple, np.ndarray)):
            rk = rk[0] if len(rk) > 0 else 0.0
        try:
            risks.append(float(rk))
        except:
            risks.append(0.0)

    x = list(range(len(stocks)))
    width = 0.35

    plt.figure(figsize=(8,5))
    plt.bar(x, returns, width=width, label='Return %', color='green', alpha=0.7)
    plt.bar([i + width for i in x], risks, width=width, label='Risk %', color='red', alpha=0.7)

    plt.xticks([i + width/2 for i in x], stocks)
    plt.ylabel("Percentage (%)")
    plt.title("Stock Comparison: Returns vs Risk")
    plt.legend()
    plt.tight_layout()

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    plt.savefig(filename)
    plt.close()

    return filename

import requests
from config import NEWS_API_KEY

def get_news(stock_name):
    url = f"https://newsapi.org/v2/everything?q={stock_name}&apiKey={NEWS_API_KEY}"
    response = requests.get(url).json()

    articles = response.get("articles", [])[:5]

    headlines = [a['title'] for a in articles]

    return headlines

import requests
import os

def ask_llm(prompt):
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
        "model": "openrouter/free",  # <-- The universal free endpoint!
        "messages": [{"role": "user", "content": prompt}]
    }
        )
        data = response.json()
        if "choices" in data:
            return data['choices'][0]['message']['content']
        else:
            return "AI unavailable right now."
    except Exception as e:
        return f"AI error: {e}"