from flask import Flask, render_template, request, jsonify, session
from agents import run_agents, financial_chat
from stock_comparison import run_stock_comparison
from tools import ask_llm
import datetime
app = Flask(__name__)
app.secret_key = "supersecretkey"

# HOME
@app.route('/')
def home():
    user_history = session.get("history", [])
    return render_template("index.html", history=user_history)

# ANALYZE STOCK
@app.route("/analyze", methods=["POST"])
def analyze():
    stock = request.form["stock"]
    income = float(request.form["income"])
    expenses = float(request.form["expenses"])
    risk = request.form["risk"]

    future_invest = request.form.get("future_invest")
    years = request.form.get("years")
    future_invest = float(future_invest) if future_invest else None
    years = int(years) if years else None

    result = run_agents(stock, income, expenses, risk, future_invest, years)

    session["income"] = income
    session["expenses"] = expenses
    session["risk"] = risk
    session["current"] = result["current"]
    session["predicted"] = result["predicted"]
    session["RSI"] = result["indicators"]["RSI"]
    session["MACD"] = result["indicators"]["MACD"]
    session["sentiment"] = result.get("sentiment_summary", {}).get("overall", "Neutral")
    session["confidence"] = result["confidence"]

    if "history" not in session:
        session["history"] = []
        
    history_entry = {
        "stock": stock.upper(),
        "decision": result["decision"],
        "price": result["current"],
        "date": datetime.datetime.now().strftime("%b %d, %H:%M")
    }
    session["history"].insert(0, history_entry)
    session["history"] = session["history"][:5] 
    session.modified = True

    return render_template("dashboard.html", data=result)

# CHAT UI
@app.route("/chat_ui")
def chat_ui():
    return render_template("result.html")

# CHAT AJAX
@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message")
    context = {
        "income": session.get("income"),
        "expenses": session.get("expenses"),
        "risk": session.get("risk"),
        "current": session.get("current"),
        "predicted": session.get("predicted"),
        "RSI": session.get("RSI"),
        "MACD": session.get("MACD"),
        "sentiment": session.get("sentiment"),
        "confidence": session.get("confidence")
    }
    reply = financial_chat(user_msg, context)
    return jsonify({"reply": reply})

# STOCK COMPARISON
@app.route("/compare", methods=["GET", "POST"])
def stock_compare():
    comparison_html = ""
    error_message = None

    if request.method == "POST":
        stocks_input = request.form.get("stocks")  # e.g., "TCS.NS, INFY.NS, RELIANCE.NS"
        if not stocks_input:
            error_message = "Please enter at least one stock symbol."
        else:
            stock_list = [s.strip().upper() for s in stocks_input.split(",")]
            try:
                result = run_stock_comparison(stock_list)
                comparison_html = result.get('html', "<p>No comparison data available.</p>")
            except Exception as e:
                error_message = f"Error during comparison: {e}"

    return render_template("compare.html", comparison_html=comparison_html, error_message=error_message)
@app.route("/clear_history", methods=["POST"])
def clear_history():
    # Remove the history list from the session cookie
    session.pop("history", None)
    session.modified = True
    return jsonify({"status": "success"})
# ---------- PAPER TRADING ----------
@app.route("/paper_trade", methods=["POST"])
def paper_trade():
    data = request.json
    stock = data.get("stock")
    price = data.get("price")
    shares = data.get("shares", 1)
    
    if "portfolio" not in session:
        session["portfolio"] = []
        
    session["portfolio"].append({
        "stock": stock,
        "buy_price": float(price),
        "shares": int(shares),
        "total_cost": float(price) * int(shares),
        "date": datetime.datetime.now().strftime("%b %d, %Y")
    })
    session.modified = True
    return jsonify({"status": "success", "message": f"Successfully purchased {shares} shares of {stock}!"})

if __name__ == "__main__":
    app.run(debug=True)