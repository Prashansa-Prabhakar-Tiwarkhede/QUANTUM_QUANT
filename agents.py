import os
import requests
from dotenv import load_dotenv
from tools import generate_trend_graph, get_news
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
import math
import re
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# ---------- LLM Function (SAFE) ----------
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
        print("COMPARE.PY AI RESPONSE:", data) # Debug print
        
        if "choices" in data:
            return data['choices'][0]['message']['content']
        else:
            return "AI unavailable right now."
    except Exception as e:
        return f"AI error: {e}"
# ---------- Confidence Score ----------
def calculate_confidence(current, predicted, indicators):
    score = 0

    if current > indicators['MA20']:
        score += 25
    else:
        score += 10

    rsi = indicators['RSI']
    if 40 <= rsi <= 60:
        score += 25
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        score += 15
    else:
        score += 5

    if indicators['MACD'] > indicators['Signal']:
        score += 30
    else:
        score += 10

    diff = abs(predicted - current) / current if current != 0 else 0
    if diff > 0.05:
        score += 20
    else:
        score += 10

    return min(score, 100)

# ---------- Stock Prediction ----------
def predict_stock(stock):
    df = yf.download(stock, period="6mo", interval="1d")

    if df.empty:
        return 0, 0, "No Data", {"RSI": 0, "MACD": 0, "Signal": 0, "MA20": 0}, 0, {"dates": [], "prices": []}

    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = close.dropna()
    current_price = round(close.iloc[-1], 2)
    
    # NEW: Extract dates and prices for the interactive chart!
    chart_dates = df.index.strftime('%b %d').tolist()
    chart_prices = [round(p, 2) for p in close.tolist()]
    chart_data = {"dates": chart_dates, "prices": chart_prices}

    if len(close) < 30:
        return current_price, current_price, "Not enough data", {"RSI": 0, "MACD": 0, "Signal": 0, "MA20": current_price}, 0, chart_data

    df["MA_20"] = SMAIndicator(close, window=20).sma_indicator()
    df["RSI"] = RSIIndicator(close).rsi()

    macd = MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()

    latest_rsi = 0 if math.isnan(df["RSI"].iloc[-1]) else df["RSI"].iloc[-1]
    latest_macd = 0 if math.isnan(df["MACD"].iloc[-1]) else df["MACD"].iloc[-1]
    latest_signal = 0 if math.isnan(df["MACD_signal"].iloc[-1]) else df["MACD_signal"].iloc[-1]
    latest_ma = current_price if math.isnan(df["MA_20"].iloc[-1]) else df["MA_20"].iloc[-1]

    predicted_price = round(current_price * 1.05, 2)

    if latest_macd > latest_signal and latest_rsi < 60: 
        decision = "BUY 📈"
    elif latest_rsi > 70 and latest_macd < latest_signal: 
        decision = "SELL 📉"
    elif current_price > latest_ma and latest_rsi < 65: 
        decision = "BUY 📈 (Momentum)"
    else: 
        decision = "HOLD 📊"

    indicators = {
        "RSI": round(latest_rsi, 2), "MACD": round(latest_macd, 2),
        "Signal": round(latest_signal, 2), "MA20": round(latest_ma, 2)
    }
    confidence = calculate_confidence(current_price, predicted_price, indicators)

    return current_price, predicted_price, decision, indicators, confidence, chart_data

# ---------- Sentiment Aggregation ----------
def aggregate_sentiment(sentiments):
    positive = sentiments.count("Positive")
    negative = sentiments.count("Negative")
    neutral = sentiments.count("Neutral")

    if positive > negative and positive > neutral:
        overall = "Positive"
    elif negative > positive and negative > neutral:
        overall = "Negative"
    else:
        overall = "Neutral"

    return {
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "overall": overall
    }


# ---------- Future Investment Simulation ----------
def simulate_future_value(investment, years, expected_return=0.12):
    future_value = investment * ((1 + expected_return) ** years)

    yearly_data = []
    value = investment

    for year in range(1, years + 1):
        value = value * (1 + expected_return)
        yearly_data.append({
            "year": year,
            "value": round(value, 2)
        })

    return round(future_value, 2), yearly_data


# ---------- Main Function ----------
def run_agents(stock, income, expenses, risk, future_invest=None, years=None):

    current, predicted, decision, indicators, confidence, chart_data = predict_stock(stock)

    savings = max(0, income - expenses)
    invest = savings * (0.4 if risk == "Low" else 0.6 if risk == "Medium" else 0.8)

    # ---------- Future Simulation ----------
    future_result = None
    yearly_growth = []
    if future_invest is not None and years is not None:
        cagr = 0.08 if risk == "Low" else 0.12 if risk == "Medium" else 0.15
        future_value, yearly_growth = simulate_future_value(future_invest, years, cagr)

        future_result = {
            "initial": future_invest,
            "years": years,
            "cagr": int(cagr * 100),
            "future_value": future_value,
            "growth": yearly_growth
        }

        future_prompt = f"User invests ${future_invest} for {years} years at {future_result['cagr']}% CAGR. Explain how compounding works short 4 lines."
        future_result["explanation"] = ask_llm(future_prompt)

    # ---------- AI Explanation ----------
    prompt = f"""
    User income: {income}, Expenses: {expenses}, Risk: {risk}
    Decision: {decision}, Invest: {invest}
    Indicators -> RSI: {indicators['RSI']}, MACD: {indicators['MACD']}
    Explain why this decision is good in 5 lines.
    """
    explanation = ask_llm(prompt)

    # ---------- Graph (FIXED: Now uses the single stock trend graph) ----------
    graph_path = generate_trend_graph(stock)

    # ---------- NEWS + SENTIMENT ----------
    headlines = get_news(stock)
    sentiment_labels = []
    detailed_sentiment = [] # We need this list format for your new frontend

    if headlines:
        for hl in headlines:
            result = ask_llm(f'Analyze sentiment: "{hl}" Output ONLY: Positive / Negative / Neutral')
            
            label = "Neutral"
            if "Positive" in result: label = "Positive"
            elif "Negative" in result: label = "Negative"
            
            sentiment_labels.append(label)
            detailed_sentiment.append(f"{hl} → {label}") # Format: "Headline -> Positive"
    else:
        detailed_sentiment = "No news available"

    sentiment_summary = aggregate_sentiment(sentiment_labels) if sentiment_labels else {}

    # Strip out the raw HTML formatter and just use our simple bullet point cleaner
    explanation_html = format_ai_insight(explanation)

    return {
        "current": current,
        "predicted": predicted,
        "decision": decision,
        "investment": round(invest, 2),
        "confidence": confidence,
        "explanation": explanation_html,
        "chart_data": chart_data,
        "news": headlines,
        "sentiment": detailed_sentiment, # Passes the list the frontend expects
        "sentiment_summary": sentiment_summary,
        "indicators": indicators,
        "future": future_result
    }

# ---------- AI Chat ----------
def financial_chat(user_msg, context):
    prompt = f"""
    User asked: {user_msg}
    Context:
    Income: {context.get('income')}
    Expenses: {context.get('expenses')}
    Risk: {context.get('risk')}
    Current Price: {context.get('current')}
    Predicted: {context.get('predicted')}
    RSI: {context.get('RSI')}
    MACD: {context.get('MACD')}
    Sentiment: {context.get('sentiment')}
    Confidence: {context.get('confidence')}

    Answer like a financial advisor in simple terms.
    """
    return ask_llm(prompt)

# ---------- HTML Formatter (FIXED: Only returns simple bullet points now!) ----------
def format_ai_insight(explanation):
    explanation_html = explanation
    explanation_html = re.sub(r'^\d+\.\s+', r'<li>', explanation_html, flags=re.MULTILINE)
    explanation_html = re.sub(r'^-\s+', r'<li>', explanation_html, flags=re.MULTILINE)
    explanation_html = explanation_html.replace('\n', '</li>')

    if '<li>' in explanation_html:
        explanation_html = f"<ul class='list-disc pl-5 space-y-2'>{explanation_html}</ul>"
        
    return explanation_html
