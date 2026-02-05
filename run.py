from playwright.sync_api import sync_playwright
import json
import copy
import re
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import os
from bs4 import BeautifulSoup
from flask_cors import CORS

with open(".env", 'r') as env:
    EMAIL = env.readline()
    PASSWORD = env.readline()

LOGIN_URL = "https://indma01.clubwise.com/upsugymandsportscentre/index.html"
CLUBWISE_URL = "https://indma01.clubwise.com/upsugymandsportscentre/WebServiceDispatcher.wso/CallAction/JSON"

STATE_FILE = "state.json"
DATE_PAYLOAD_FILE = "date_payload.json"
SHOW_PAYLOAD_FILE = "show_payload.json"

HEADERS = {
    "Content-Type": "application/json"
}

def update_cache():
    print("Refreshing session with Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        show_payload = None
        date_payload = None

        def capture_request(request):
            nonlocal show_payload, date_payload

            if "CallAction/JSON" not in request.url or request.method != "POST":
                return

            data = json.loads(request.post_data)

            action = data["ActionRequest"]["aActions"][0]["sAction"]

            if action == "mChangeDate":
                date_payload = data
                print("Captured date payload")

            elif action == "OnShow":
                show_payload = data
                print("Captured show payload")

        context.on("request", capture_request)

        page.goto(LOGIN_URL)

        page.fill("input[type=email]", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.click("text=Sign In")

        page.click("text=continue")
        page.click("text=Make a booking")
        page.click("text=Book by Activity")
        page.click("text=Badminton")
        page.click("div[role=Next]")
        page.click("div[role=Next]")

        page.wait_for_timeout(5000)

        if not show_payload or not date_payload:
            raise RuntimeError("Could not capture payloads")

        context.storage_state(path=STATE_FILE)

        with open(DATE_PAYLOAD_FILE, "w") as f:
            json.dump(date_payload, f)

        with open(SHOW_PAYLOAD_FILE, "w") as f:
            json.dump(show_payload, f)

        browser.close()

    print("Session + payload cache refreshed")

def get_session():
    session = requests.Session()

    with open(STATE_FILE) as f:
        state = json.load(f)

    for c in state["cookies"]:
        session.cookies.set(
            c["name"],
            c["value"],
            domain=c["domain"],
            path=c["path"]
        )

    return session

def set_payload_date(payload: dict, new_date: str) -> dict:
    data = copy.deepcopy(payload)

    dt = datetime.strptime(new_date, "%d/%m/%Y")
    iso_date = dt.strftime("%Y-%m-%d")
    pretty_date = dt.strftime("%A %d/%m/%Y")

    header = data["ActionRequest"]["Header"]

    for sync in header["aSyncProps"]:
        if sync.get("sO") == "oMulticourtGrid.oMCG":
            for prop in sync["aP"]:
                if prop["sN"] == "pdCurrentDate":
                    prop["sV"] = new_date

    for sync in header["aSyncProps"]:
        for prop in sync.get("aP", []):
            if prop.get("sN") == "psHtml":
                html = prop["sV"]

                html = re.sub(r"\d{2}/\d{2}/\d{4}", new_date, html)
                html = re.sub(r"\d{4}-\d{2}-\d{2}", iso_date, html)

                html = re.sub(
                    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) \d{2}/\d{2}/\d{4}",
                    pretty_date,
                    html
                )

                prop["sV"] = html

    return data

def extract_slots_only(data: dict):
    sync = data["Header"]["aSyncProps"]

    grid_html = ""
    hours_html = ""

    for s in sync:
        if s["sO"].endswith("oHoursLabelHTML"):
            hours_html = s["aP"][0]["sV"]
        if s["sO"].endswith("oMulticourtGridHTML"):
            grid_html = s["aP"][0]["sV"]

    soup_hours = BeautifulSoup(hours_html, "html.parser")
    soup_grid = BeautifulSoup(grid_html, "html.parser")

    times = [t.text.strip() for t in soup_hours.select(".courtTime div")]

    rows = soup_grid.select(".courtGridRow")

    slots = []

    for i, row in enumerate(rows):
        cells = row.select(".courtGridCell")

        free = [
            "courtBooked" not in cell.get("class", [])
            for cell in cells
        ]

        slots.append({
            "time": times[i],
            "free": free
        })

    return slots

def call_clubwise(date: str):
    if not os.path.exists(STATE_FILE):
        update_cache()

    session = get_session()

    with open(DATE_PAYLOAD_FILE) as f:
        date_payload = json.load(f)

    with open(SHOW_PAYLOAD_FILE) as f:
        show_payload = json.load(f)

    r = session.post(
        CLUBWISE_URL,
        headers=HEADERS,
        json=set_payload_date(date_payload, date)
    )

    if r.status_code != 200:
        update_cache()
        return call_clubwise(date)

    r = session.post(
        CLUBWISE_URL,
        headers=HEADERS,
        json=set_payload_date(show_payload, date)
    )

    return r.json()

app = Flask(__name__)


@app.route("/api/bookings")
def bookings():
    date = request.args.get("date")

    if not date:
        return {"error": "date required (DD/MM/YYYY)"}, 400

    raw = call_clubwise(date)

    return jsonify(extract_slots_only(raw))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    CORS(app)
