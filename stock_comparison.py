import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Disable GUI backend for Flask
import matplotlib.pyplot as plt
import os
import requests
from config import NEWS_API_KEY
from dotenv import load_dotenv

load_dotenv()
# -------------------- STOCK DATA & PREDICTION --------------------
def get_stock_data(stock):
    df = yf.download(stock, period="6mo", interval="1d")
    return df

def predict_stock(stock):
    df = get_stock_data(stock)
    if df is None or df.empty or len(df) < 10:
        return None, None, "Not enough data"

    df = df[['Close']].copy()
    df['Days'] = np.arange(len(df))

    X = df[['Days']]
    y = df['Close']

    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(X, y)

    next_day = np.array([[len(df)]])
    current = float(df["Close"].tail(1).iloc[0])  # Safe scalar
    prediction = float(model.predict(next_day)[0])  # Safe scalar

    change = ((prediction - current) / current) * 100
    if change > 2:
        decision = "BUY"
    elif change < -2:
        decision = "SELL"
    else:
        decision = "HOLD"

    return round(current, 2), round(prediction, 2), decision

# -------------------- NEWS & SENTIMENT --------------------
def get_news(stock_name):
    url = f"https://newsapi.org/v2/everything?q={stock_name}&apiKey={NEWS_API_KEY}"
    response = requests.get(url).json()
    articles = response.get("articles", [])[:5]
    return [a['title'] for a in articles]

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

# -------------------- STOCK COMPARISON --------------------
def compare_stocks(stocks):
    comparison = []

    for stock in stocks:
        df = get_stock_data(stock)
        if df.empty:
            comparison.append({
                "stock": stock,
                "current": 0,
                "return_percent": 0,
                "risk": 0,
                "sentiment": "No Data"
            })
            continue

        close = df["Close"].dropna()
        current_price = float(close.tail(1).iloc[0])
        start_price = float(close.head(1).iloc[0])

        # ---------- Returns ----------
        return_percent = round(((current_price - start_price) / start_price) * 100, 2)

        # ---------- Risk / Volatility ----------
        daily_returns = close.pct_change().dropna()
        risk = round(daily_returns.std() * 100, 2)

        # ---------- News & Sentiment ----------
        headlines = get_news(stock)
        sentiment_labels = []
        for hl in headlines:
            sentiment_prompt = f'Analyze sentiment: "{hl}" Output only Positive/Negative/Neutral.'
            result = ask_llm(sentiment_prompt)
            if "Positive" in result:
                sentiment_labels.append("Positive")
            elif "Negative" in result:
                sentiment_labels.append("Negative")
            else:
                sentiment_labels.append("Neutral")

        positive = sentiment_labels.count("Positive")
        negative = sentiment_labels.count("Negative")
        neutral = sentiment_labels.count("Neutral")

        if positive > negative and positive > neutral:
            overall_sentiment = "Positive"
        elif negative > positive and negative > neutral:
            overall_sentiment = "Negative"
        else:
            overall_sentiment = "Neutral"

        comparison.append({
            "stock": stock,
            "current": round(current_price, 2),
            "return_percent": return_percent,
            "risk": risk,
            "sentiment": overall_sentiment
        })

    return comparison

# -------------------- GRAPH GENERATION --------------------
def generate_comparison_graph(comparison_data, filename="static/stock_comparison.png"):
    stocks = [d['stock'] for d in comparison_data]
    returns = [float(d['return_percent']) for d in comparison_data]
    risks = [float(d['risk']) for d in comparison_data]

    x = range(len(stocks))
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

# -------------------- HTML FORMATTER --------------------
def format_comparison_html(comparison_data, graph_path):
    html = "<h2>📊 Stock Comparison</h2>"
    html += f"<img src='/{graph_path}' alt='Comparison Graph' style='max-width:700px;'><br><br>"
    html += "<table border='1' style='border-collapse: collapse; width:100%'>"
    html += "<tr><th>Stock</th><th>Current Price ($)</th><th>6-Month Return (%)</th><th>Volatility (%)</th><th>Sentiment</th></tr>"

    for data in comparison_data:
        color = "green" if data["sentiment"] == "Positive" else "red" if data["sentiment"] == "Negative" else "orange"
        html += f"<tr><td>{data['stock']}</td><td>{data['current']}</td><td>{data['return_percent']}</td><td>{data['risk']}</td><td style='color:{color};'>{data['sentiment']}</td></tr>"

    html += "</table>"
    return html

# -------------------- MAIN FUNCTION --------------------
def run_stock_comparison(stocks):
    comparison_data = compare_stocks(stocks)
    graph_path = generate_comparison_graph(comparison_data)
    html = format_comparison_html(comparison_data, graph_path)
    return {
        "data": comparison_data,
        "graph": graph_path,
        "html": html
    }

# -------------------- EXAMPLE USAGE --------------------
if __name__ == "__main__":
    stocks = ["TCS.NS", "INFY.NS", "RELIANCE.NS"]
    result = run_stock_comparison(stocks)
    print(result['html'])