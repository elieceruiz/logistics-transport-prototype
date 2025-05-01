import streamlit as st from datetime import datetime from pymongo import MongoClient from dotenv import load_dotenv import os import pytz import requests

Configuración inicial

st.set_page_config(page_title="ZARA – Logistics Prototype", layout="centered")

Zona horaria Bogotá

tz = pytz.timezone("America/Bogota")

Cargar variables de entorno

load_dotenv()

Conexión MongoDB

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://elieceruiz_admin:fPydI3B73ijAukEz@cluster0.rqzim65.mongodb.net/zara_db?retryWrites=true&w=majority&appName=Cluster0") client = MongoClient(MONGO_URI) db = client["zara_db"] collection = db["logistics_interactions"]

Registrar acceso y notificar vía Telegram

def log_and_notify_access(): try: ip_data = requests.get("https://ipinfo.io").json() ip = ip_data.get("ip", "N/A") city = ip_data.get("city", "Unknown") country = ip_data.get("country", "Unknown")

message = f"⚠️ Nueva visita a la app\nIP: {ip}\nUbicación: {city}, {country}"

    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = {"chat_id": telegram_chat_id, "text": message}
        requests.post(url, data=data)

    db["access_logs"].insert_one({
        "timestamp": datetime.now(tz).isoformat(),
        "ip": ip,
        "city": city,
        "country": country
    })

except Exception as e:
    print("Error al registrar acceso:", e)

Ejecutar al inicio

log_and_notify_access()

Escenarios

scenarios = { "Lost order": { "description": "Customer claims they did not receive their order, even though it's marked as delivered.", "steps": [ "✔️ Greet the customer and validate identity following DPA: collect at least 3 of the following — order number, email, associated phone, full name.", "✔️ Open GIPI and verify the order status.", "✔️ If marked as 'Delivered', ask if someone else might have received it.", "✔️ If customer denies receipt, open BO case using MOCA template: 'Lost Order'.", "✔️ Inform the customer that investigation may take up to 72 hours and they will be contacted by logistics." ], "moca_template": "Lost Order" }, "New delivery attempt": { "description": "Customer requests a second delivery attempt after the first one failed.", "steps": [ "✔️ Greet the customer and validate identity following DPA: collect at least 3 of the following — order number, email, associated phone, full name.", "✔️ Check GIPI for failed delivery attempt.", "✔️ Use MOCA template: 'Reschedule Delivery' to document request.", "✔️ Confirm new attempt with the customer and share the estimated delivery date." ], "moca_template": "Reschedule Delivery" }, "Partial delivery": { "description": "Customer received only part of the order; some items are missing.", "steps": [ "✔️ Greet the customer and validate identity following DPA: collect at least 3 of the following — order number, email, associated phone, full name.", "✔️ Ask the customer which items were missing.", "✔️ Check in GIPI if the order was shipped in multiple packages.", "✔️ If items are in transit, provide ETA. If not, use MOCA template: 'Missing Items'." ], "moca_template": "Missing Items" } }

Tabs

tab1, tab2, tab3 = st.tabs(["Register Interaction", "History", "Access Logs"])

TAB 1 – Registro

with tab1: st.title("ZARA – Logistics Transport Prototype") st.markdown("Start typing to search or select a case reason.")

selected = st.selectbox(
    "Select reason:",
    options=list(scenarios.keys()),
    index=None,
    placeholder="Start typing or choose a scenario..."
)

if selected:
    st.subheader("Scenario Description")
    st.markdown(scenarios[selected]["description"])

    st.subheader("Step-by-Step")
    for i, step in enumerate(scenarios[selected]["steps"]):
        st.checkbox(step, key=f"step_{i}")

    st.subheader("Suggested MOCA Template")
    st.markdown(f"**{scenarios[selected]['moca_template']}**")

    st.subheader("Agent Notes")
    notes = st.text_area("Add relevant notes here:")

    if st.button("Save Interaction"):
        doc = {
            "timestamp": datetime.now(tz).isoformat(),
            "category": selected,
            "steps": scenarios[selected]["steps"],
            "moca_template": scenarios[selected]["moca_template"],
            "notes": notes
        }
        collection.insert_one(doc)
        st.success("Interaction saved to MongoDB successfully!")

TAB 2 – Historial

with tab2: st.title("Interaction History") docs = list(collection.find().sort("timestamp", -1))

if not docs:
    st.info("No interactions found yet.")
else:
    data = []
    for doc in docs:
        data.append({
            "Date": doc["timestamp"][:19].replace("T", " "),
            "Category": doc["category"],
            "MOCA Template": doc["moca_template"],
            "Notes": doc.get("notes", "")
        })

    st.dataframe(data, use_container_width=True)

TAB 3 – Logs de acceso

with tab3: st.title("Access Logs") logs = list(db["access_logs"].find().sort("timestamp", -1))

if not logs:
    st.info("No access logs found.")
else:
    log_data = []
    for log in logs:
        log_data.append({
            "Date": log["timestamp"][:19].replace("T", " "),
            "IP": log.get("ip", "-"),
            "City": log.get("city", "-"),
            "Country": log.get("country", "-")
        })

    st.dataframe(log_data, use_container_width=True)

