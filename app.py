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


def extract_countries(product):
    tags = product.get("countries_tags")
    if isinstance(tags, list) and tags:
        return ", ".join(
            c.replace("en:", "").replace("-", " ").title()
            for c in tags
        )

    countries = product.get("countries")
    if isinstance(countries, str) and countries.strip():
        return countries

    return "Not available"


def estimate_price_eur(product):
    name = (product.get("product_name") or "").lower()
    categories = (product.get("categories") or "").lower()
    quantity = (product.get("quantity") or "").lower()

    # ----------------------------
    # 1. BASE PRICE
    # ----------------------------
    price = 2.49  # realistic EU baseline

    if any(x in categories for x in ["chocolate", "snack", "biscuit"]):
        price = 1.99
    elif any(x in categories for x in ["drink", "beverage", "juice", "water"]):
        price = 1.39
    elif any(x in categories for x in ["dairy", "milk", "cheese", "yogurt"]):
        price = 2.19
    elif any(x in categories for x in ["pet", "dog", "cat"]):
        price = 4.49
    elif any(x in categories for x in ["cosmetic", "beauty", "shampoo"]):
        price = 3.49
    elif any(x in categories for x in ["cleaning", "household"]):
        price = 2.79

    # ----------------------------
    # 2. BRAND ADJUSTMENT
    # ----------------------------
    premium_brands = ["coca", "nestle", "pepsi", "loreal", "nivea"]
    budget_brands = ["lidl", "chef select", "freeway", "milbona"]

    if any(b in name for b in premium_brands):
        price *= 1.35
    elif any(b in name for b in budget_brands):
        price *= 0.9

    # ----------------------------
    # 3. QUANTITY ADJUSTMENT
    # ----------------------------
    if any(x in quantity for x in ["1kg", "1000g", "1l", "1000ml"]):
        price *= 1.25
    elif any(x in quantity for x in ["500g", "500ml"]):
        price *= 1.1
    elif any(x in quantity for x in ["200g", "250g", "150ml"]):
        price *= 0.85
    elif any(x in quantity for x in ["100g", "100ml"]):
        price *= 0.7

    # ----------------------------
    # 4. SPECIAL ATTRIBUTES
    # ----------------------------
    if any(x in name for x in ["organic", "bio"]):
        price *= 1.25

    # ----------------------------
    # 5. ROUNDING (RETAIL STYLE)
    # ----------------------------
    price = round(price, 2)
    if price > 1:
        price = round(price - 0.01, 2)

    return f"~€{price:.2f}"


# ----------------------------
# CONFIDENCE WITH FACTORS
# ----------------------------
def calculate_confidence(product, query, is_upc_search=False):
    score = 0
    factors = {
        "name": False,
        "category": False,
        "upc": False,
        "country": False,
    }

    name = (product.get("product_name") or "").lower()
    categories = (product.get("categories") or "").lower()

    if query.lower() in name:
        score += 50
        factors["name"] = True

    if categories:
        score += 20
        factors["category"] = True

    if is_upc_search:
        score += 40
        factors["upc"] = True

    if extract_countries(product) != "Not available":
        score += 10
        factors["country"] = True

    return min(score, 100), factors


def format_product(p, source, query=None, upc=None, is_upc_search=False):
    confidence, factors = calculate_confidence(p, query or "", is_upc_search)

    return {
        "product_name": p.get("product_name") or "Unknown product",
        "upc": upc or p.get("code"),
        "image": p.get("image_url"),
        "price": estimate_price_eur(p),
        "countries": extract_countries(p),
        "source": source,
        "confidence": confidence,
        "confidence_factors": factors,
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
                "page_size": 3,
            }
            r = requests.get(src["search"], params=params, timeout=6)
            if r.status_code != 200:
                continue

            for p in r.json().get("products", []):
                results.append(format_product(p, src["name"], query=query))
        except Exception:
            continue

    return results


def get_product_by_upc(upc):
    results = []

    for src in SOURCES:
        try:
            r = requests.get(src["upc"].format(upc), timeout=6)
            if r.status_code == 200 and r.json().get("status") == 1:
                results.append(
                    format_product(
                        r.json()["product"],
                        src["name"],
                        query=upc,
                        upc=upc,
                        is_upc_search=True,
                    )
                )
        except Exception:
            continue

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

    results = get_product_by_upc(query) if is_upc(query) else search_products(query)
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
<title>Product Price Chatbot 🤖 v2</title>
<style>
body { font-family: Arial; background:#f4f4f4; }
.chat { width:560px; margin:30px auto; background:#fff; padding:16px; border-radius:8px; }
.msg { margin-bottom:14px; }
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

.conf { font-size:13px; }
.info { cursor:pointer; color:#1a73e8; font-weight:bold; }

.popup {
  display:none;
  position:absolute;
  background:#fff;
  border:1px solid #ccc;
  padding:10px;
  font-size:12px;
  width:260px;
  z-index:1000;
}

.factor-on { color:#AB1818; font-weight:bold; }
.factor-off { color:#999; }

/* 🔴 CONFIDENCE COLOR */
.confidence-red {
  color: #d93025;
  font-weight: bold;
}
</style>
</head>

<body>

<div class="chat">
<a href="/logout" style="float:right">Logout</a>
<h3>Product Price Chatbot 🤖 v2</h3>

<div class="instructions">
<b>Step 1:</b> Refer the official LIDL product portfolios from below:<br><br>
⭐ <a href="https://www.lidl.de/c/online-prospekte/s10005610" target="_blank">Germany </a>
⭐ <a href="https://www.lidl.cz/c/akcni-letak/s10008644" target="_blank">Czech Republic</a>
⭐ <a href="https://www.lidl.co.uk/c/online-leaflets/s10023175" target="_blank">United Kingdom</a>
⭐ <a href="https://www.lidl.pl/c/nasze-gazetki/s10008614" target="_blank">Poland</a><br><br>
<b>Step 2:</b> Search by product name or UPC if not found above.
</div>

<div id="chat"></div>

<input id="q" placeholder="Enter product name or UPC" style="width:75%">
<button onclick="send()">Send</button>
</div>

<div id="popup" class="popup"></div>

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
      chat.innerHTML += `<div class="msg bot">No product found.</div>`;
      return;
    }

    data.results.forEach(p => {
      chat.innerHTML += `
      <div class="msg bot">
        <b>${p.product_name}</b><br>
        UPC: ${p.upc || "N/A"}<br>
        Estimated Price: ${p.price}<br>
        Countries where sold: ${p.countries}<br>
        Source: ${p.source}<br>
        <div class="conf">
          Confidence: <span class="confidence-red">${p.confidence}%</span>
          <span class="info" onclick='togglePopup(event, ${JSON.stringify(p.confidence_factors)})'>ℹ️</span>
        </div>
        ${p.image ? `<img src="${p.image}">` : ""}
      </div>`;
    });
  });

  document.getElementById("q").value = "";
}

function togglePopup(e, factors){
  let p = document.getElementById("popup");

  if (p.style.display === "block") {
    p.style.display = "none";
    return;
  }

  p.innerHTML = `
    <b>Confidence score calculation</b><br><br>
    <div class="${factors.name ? 'factor-on' : 'factor-off'}">• Product name match (50%)</div>
    <div class="${factors.category ? 'factor-on' : 'factor-off'}">• Category relevance (20%)</div>
    <div class="${factors.upc ? 'factor-on' : 'factor-off'}">• Exact UPC match (40%)</div>
    <div class="${factors.country ? 'factor-on' : 'factor-off'}">• Country metadata present (10%)</div>
  `;

  p.style.display = "block";
  p.style.top = (e.pageY + 10) + "px";
  p.style.left = (e.pageX + 10) + "px";
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
