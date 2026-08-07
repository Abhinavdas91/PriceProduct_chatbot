import os
import requests
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
import concurrent.futures

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
def fetch_search_results(src, query):
    """Fetches search results from a single source."""
    try:
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
        }
        r = requests.get(src["search"], params=params, timeout=5)
        if r.status_code == 200:
            return [format_product(p, src["name"]) for p in r.json().get("products", [])[:7]]
    except Exception:
        pass
    return []

def search_products(query):
    """Searches for products across all sources concurrently."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as executor:
        future_to_source = {executor.submit(fetch_search_results, src, query): src for src in SOURCES}
        for future in concurrent.futures.as_completed(future_to_source):
            try:
                results.extend(future.result())
            except Exception:
                pass
    return results

def get_product_by_upc(upc):
    """Searches for a product by UPC across all sources sequentially until found."""
    for src in SOURCES:
        try:
            r = requests.get(src["upc"].format(upc), timeout=5)
            if r.status_code == 200 and r.json().get("status") == 1:
                return [format_product(r.json()["product"], src["name"], upc)]
        except Exception:
            pass
    return []


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
<title>Product Price Bot</title>
<style>
body { font-family: Arial; background:#f4f4f4; }
.chat { width:520px; margin:30px auto; background:#fff; padding:16px; border-radius:8px; }
.msg { margin-bottom:12px; }
.user { color:#1a73e8; }
.bot { color:#188038; border-bottom:1px solid #eee; padding-bottom:10px; }
img { max-width:120px; margin-top:6px; border-radius:4px; }
.instructions {
  background:#f9fafb;
  border-left:4px solid #1a73e8;
  padding:10px;
  margin-bottom:15px;
  font-size:14px;
}
</style>
</head>
<body>

<div class="chat">
<a href="/logout" style="float:right">Logout</a>
<h3>Product Price Bot</h3>

<div class="instructions">
  <b>Hint:</b> You can search for a product by its name or by its UPC/barcode number.
</div>

<div id="chat"></div>

<input id="q" placeholder="Enter product name or UPC" style="width:75%">
<button onclick="send()">Send</button>
</div>

<script>
function send(){
  let q = document.getElementById("q").value;
  if(!q) return;

  let chat = document.getElementById("chat");
  chat.innerHTML += `<div class="msg user"><b>You:</b> ${q}</div>`;
  document.getElementById("q").value = "";

  fetch("/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query: q})
  })
  .then(r => r.json())
  .then(data => {
    if(data.results.length === 0){
      chat.innerHTML += `<div class="msg bot">
        <b>Product not found.</b><br>
        Please try a different product name or UPC.
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
    chat.scrollTop = chat.scrollHeight;
  });
}

// Allow sending with Enter key
document.getElementById("q").addEventListener("keyup", function(event) {
    if (event.key === "Enter") {
        send();
    }
});
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
