import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
import urllib.parse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")

################################
# PASSWORD (CHANGE THIS)
################################
APP_PASSWORD = os.environ.get("APP_PASSWORD", "lidl123")

################################
# CONFIG
################################

LIDL_SITES = {
    "Germany": "https://www.lidl.de",
    "UK": "https://www.lidl.co.uk",
    "Poland": "https://www.lidl.pl",
    "Netherlands": "https://www.lidl.nl",
    "USA": "https://www.lidl.com"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

################################
# HELPERS
################################

def is_upc(text):
    return text.isdigit() and 8 <= len(text) <= 14

################################
# LIDL SCRAPER (BEST EFFORT)
################################

def scrape_lidl(region, base_url, query):
    results = []
    search_url = f"{base_url}/search?query={urllib.parse.quote(query)}"

    try:
        r = requests.get(search_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("article")[:5]

        for c in cards:
            name = c.select_one("h3")
            price = c.select_one("[data-testid='price']")
            img = c.select_one("img")

            if not name:
                continue

            results.append({
                "product_name": name.text.strip(),
                "price": price.text.strip() if price else "Not available",
                "image": img["src"] if img and img.get("src") else None,
                "upc": None,
                "retailer": "LIDL",
                "region": region,
                "source": base_url
            })
    except Exception:
        pass

    return results

################################
# OPENFOODFACTS
################################

def openfoodfacts_search(query):
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1
    }

    r = requests.get(url, params=params, timeout=10)
    results = []

    if r.status_code == 200:
        for p in r.json().get("products", [])[:5]:
            results.append({
                "product_name": p.get("product_name"),
                "price": "Not available",
                "image": p.get("image_url"),
                "upc": p.get("code"),
                "retailer": "LIDL",
                "region": "Multiple",
                "source": "OpenFoodFacts"
            })

    return results


def openfoodfacts_by_upc(upc):
    url = f"https://world.openfoodfacts.org/api/v0/product/{upc}.json"
    r = requests.get(url, timeout=10)

    if r.status_code == 200 and r.json().get("status") == 1:
        p = r.json()["product"]
        return [{
            "product_name": p.get("product_name"),
            "price": "Not available",
            "image": p.get("image_url"),
            "upc": upc,
            "retailer": "LIDL",
            "region": "Multiple",
            "source": "OpenFoodFacts"
        }]
    return []

################################
# LOGIN
################################

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        error = "Invalid password"

    return render_template_string("""
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
    """, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>LIDL Product Chatbot</title>
<style>
body { font-family: Arial; background:#f4f4f4; }
.chat { width:480px; margin:40px auto; background:#fff; padding:15px; border-radius:8px; }
.msg { margin-bottom:10px; }
.user { color:#1a73e8; }
.bot { color:#188038; border-bottom:1px solid #eee; padding-bottom:8px; }
img { max-width:100px; }
</style>
</head>
<body>

<div class="chat">
<a href="/logout" style="float:right">Logout</a>
<h3>LIDL Product Chatbot</h3>
<div id="chat"></div>
<input id="q" placeholder="Product name or UPC" style="width:75%">
<button onclick="send()">Send</button>
</div>

<script>
function send(){
    let q=document.getElementById("q").value;
    if(!q) return;
    chat.innerHTML+=`<div class="msg user"><b>You:</b> ${q}</div>`;
    fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({query:q})})
    .then(r=>r.json()).then(data=>{
        if(data.results.length===0)
            chat.innerHTML+=`<div class="msg bot">No results found</div>`;
        data.results.forEach(p=>{
            chat.innerHTML+=`
            <div class="msg bot">
            <b>${p.product_name||"Unknown"}</b><br>
            Price: ${p.price}<br>
            Region: ${p.region}<br>
            Source: ${p.source}<br>
            ${p.upc ? "UPC: "+p.upc+"<br>" : ""}
            ${p.image ? `<img src="${p.image}">` : ""}
            </div>`;
        });
    });
    document.getElementById("q").value="";
}
</script>
</body>
</html>
""")


@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    query = request.json.get("query", "").strip()
    results = []

    if is_upc(query):
        results = openfoodfacts_by_upc(query)
        if results and results[0].get("product_name"):
            for region, url in LIDL_SITES.items():
                results.extend(scrape_lidl(region, url, results[0]["product_name"]))
    else:
        for region, url in LIDL_SITES.items():
            results.extend(scrape_lidl(region, url, query))
        if not results:
            results = openfoodfacts_search(query)

    return jsonify({"results": results})

################################
#(RENDER COMPATIBLE)
################################

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
