import os
import requests
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

# ----------------------------
# APP SETUP
# ----------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "lidl123")

# ----------------------------
# DATA SOURCES
# ----------------------------
SOURCES = [
    {
        "name": "OpenFoodFacts",
        "search": "https://world.openfoodfacts.org/cgi/search.pl",
        "upc": "https://world.openfoodfacts.org/api/v0/product/{}.json",
    },
    {
        "name": "OpenBeautyFacts",
        "search": "https://world.openbeautyfacts.org/cgi/search.pl",
        "upc": "https://world.openbeautyfacts.org/api/v0/product/{}.json",
    },
    {
        "name": "OpenPetFoodFacts",
        "search": "https://world.openpetfoodfacts.org/cgi/search.pl",
        "upc": "https://world.openpetfoodfacts.org/api/v0/product/{}.json",
    },
    {
        "name": "OpenProductsFacts",
        "search": "https://world.openproductsfacts.org/cgi/search.pl",
        "upc": "https://world.openproductsfacts.org/api/v0/product/{}.json",
    },
]

# ----------------------------
# HELPERS
# ----------------------------
def is_upc(text):
    return text.isdigit() and 8 <= len(text) <= 14


def estimate_price_eur(product):
    name = (product.get("product_name") or "").lower()
    categories = (product.get("categories") or "").lower()
    quantity = (product.get("quantity") or "").lower()

    price = 2.5  # base EUR

    if any(x in categories for x in ["chocolate", "snack", "biscuit"]):
        price = 2.0
    elif any(x in categories for x in ["drink", "beverage", "juice"]):
        price = 1.5
    elif any(x in categories for x in ["dairy", "milk", "cheese"]):
        price = 2.2
    elif any(x in categories for x in ["pet", "dog", "cat"]):
        price = 4.0
    elif any(x in categories for x in ["cosmetic", "beauty", "shampoo"]):
        price = 3.8
    elif "electronics" in categories:
        price = 15.0

    premium_brands = ["coca", "nestle", "pepsi", "loreal", "nivea"]
    if any(b in name for b in premium_brands):
        price *= 1.4

    if any(x in quantity for x in ["1l", "kg", "1000"]):
        price *= 1.3
    elif any(x in quantity for x in ["200g", "250g", "150ml"]):
        price *= 0.85

    return f"~€{price:.2f}"


def format_product(p, source, upc=None):
    return {
        "product_name": p.get("product_name") or "Unknown product",
        "upc": upc or p.get("code"),
        "image": p.get("image_url"),
        "price": estimate_price_eur(p),
        "region": "EU (estimated)",
        "source": source,
    }

# ----------------------------
# SEARCH LOGIC
# ----------------------------
def search_products(query):
    results = []

    for src in SOURCES:
        try:
            params = {
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
            }
            r = requests.get(src["search"], params=params, timeout=8)
            if r.status_code != 200:
                continue

            for p in r.json().get("products", [])[:3]:
                results.append(format_product(p, src["name"]))
        except Exception:
            pass

    return results


def get_product_by_upc(upc):
    results = []

    for src in SOURCES:
        try:
            r = requests.get(src["upc"].format(upc), timeout=8)
            if r.status_code == 200 and r.json().get("status") == 1:
                results.append(format_product(r.json()["product"], src["name"], upc))
        except Exception:
            pass

    return results


# ----------------------------
# AUTH
# ----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        error = "Invalid password"
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ----------------------------
# UI
# ----------------------------
@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(CHAT_HTML)


# ----------------------------
# CHAT API
# ----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    query = request.json.get("query", "").strip()
    if not query:
        return jsonify({"results": []})

    if is_upc(query):
        results = get_product_by_upc(query)
    else:
        results = search_products(query)

    return jsonify({"results": results})


# ----------------------------
# HTML
# ----------------------------
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<body style="font-family:Arial">
<h3>Login</h3>
<form method="post">
  <input type="password" name="password" placeholder="Password">
  <button type="submit">Login</button>
  <p style="color:red;">{{error}}</p>
</form>
</body>
</html>
"""

CHAT_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>LIDL Product Chatbot</title>
<style>
body { font-family: Arial; background:#f4f4f4; }
.chat { width:520px; margin:30px auto; background:#fff; padding:16px; border-radius:8px; }
.msg { margin-bottom:12px; }
.user { color:#1a73e8; }
.bot { color:#188038; border-bottom:1px solid #eee; padding-bottom:10px; }
img { max-width:120px; margin-top:6px; }
.instructions {
  background:#f9fafb;
  border-left:4px solid #1a73e8;
  padding:10px;
  margin-bottom:15px;
  font-size:14px;
}
.instructions a {
  color:#1a73e8;
  text-decoration:none;
}
.instructions a:hover {
  text-decoration:underline;
}
</style>
</head>
<body>

<div class="chat">
<a href="/logout" style="float:right">Logout</a>
<h3>LIDL Product Chatbot</h3>

<div class="instructions">
<b>Step 1:</b> Please refer the products from the official LIDL portfolios below:<br><br>

• <a href="https://www.lidl.de/c/online-prospekte/s10005610" target="_blank">
Germany – Online Prospekt
</a><br>

• <a href="https://www.lidl.cz/c/akcni-letak/s10008644" target="_blank">
Czech Republic – Akční leták
</a><br>

• <a href="https://www.lidl.co.uk/c/online-leaflets/s10023175?utm_source=home-page&utm_medium=leaflets&utm_campaign=new-navigation" target="_blank">
United Kingdom – Online Leaflets
</a><br>

• <a href="https://www.lidl.pl/c/nasze-gazetki/s10008614" target="_blank">
Poland – Gazetki
</a><br><br>

<b>Step 2:</b> If the product is <u>not available</u> in the above portfolios,  
please search using the chatbot below.
</div>

<div id="chat"></div>

<input id="q" placeholder="Enter product name or UPC" style="width:75%">
<button onclick="send()">Send</button>
</div>

<script>
function send(){
  let q = document.getElementById("q").value;
  if(!q) return;

  chat.innerHTML += `<div class="msg user"><b>You:</b> ${q}</div>`;

  fetch("/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query: q})
  })
  .then(r => r.json())
  .then(data => {
    if(data.results.length === 0){
      chat.innerHTML += `<div class="msg bot">
        Product not found.<br>
        Please verify using LIDL portfolios above or refine your search.
      </div>`;
      return;
    }

    data.results.forEach(p => {
      chat.innerHTML += `
      <div class="msg bot">
        <b>${p.product_name}</b><br>
        UPC: ${p.upc || "N/A"}<br>
        Estimated Price: ${p.price}<br>
        Region: ${p.region}<br>
        Source: ${p.source}<br>
        ${p.image ? `<img src="${p.image}">` : ""}
      </div>`;
    });
  });

  document.getElementById("q").value = "";
}
</script>

</body>
</html>
"""

# ----------------------------
# START
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
