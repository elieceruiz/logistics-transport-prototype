import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import pytz
import requests

# Carga de variables de entorno
load_dotenv()

# Configuración de página
st.set_page_config(page_title="ZARA - Logistics Prototype", layout="centered")
tz = pytz.timezone("America/Bogota")

# MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["zara_db"]
collection = db["logistics_interactions"]

# Inserta el JavaScript para obtener IP y guardarla como cookie, y también para obtener el navegador
components.html(
    """
    <script>
    if (!document.cookie.includes("client_ip")) {
        fetch("https://api.ipify.org?format=json")
            .then(response => response.json())
            .then(data => {
                document.cookie = "client_ip=" + data.ip + "; path=/";
                location.reload();
            });
    }

    // Captura el navegador y sistema operativo
    var userAgent = navigator.userAgent;
    if (!document.cookie.includes("client_user_agent")) {
        document.cookie = "client_user_agent=" + userAgent + "; path=/";
    }
    </script>
    """,
    height=0
)

# Intentamos leer la IP y el User-Agent con streamlit_javascript
try:
    import streamlit_javascript as stj
    cookie_js = stj.st_javascript("document.cookie")
    client_ip = cookie_js.split("client_ip=")[-1].split(";")[0] if "client_ip=" in cookie_js else None
    client_user_agent = cookie_js.split("client_user_agent=")[-1].split(";")[0] if "client_user_agent=" in cookie_js else None
except Exception:
    client_ip = None
    client_user_agent = None

# Registrar acceso
def log_and_notify_access(ip, user_agent):
    try:
        ip_data = requests.get(f"https://ipinfo.io/{ip}/json").json() if ip else {}
        city = ip_data.get("city", "Unknown")
        country = ip_data.get("country", "Unknown")

        # Telegram
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if telegram_token and telegram_chat_id:
            message = f"⚠️ Nueva visita a la app\nIP: {ip or 'N/A'}\nUbicación: {city}, {country}\nNavegador: {user_agent or 'N/A'}"
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            requests.post(url, data={"chat_id": telegram_chat_id, "text": message})

        # Mongo
        db["access_logs"].insert_one({
            "timestamp": datetime.now(tz).isoformat(),
            "ip": ip or "N/A",
            "city": city,
            "country": country,
            "user_agent": user_agent or "N/A"
        })
    except Exception as e:
        st.error(f"Error registrando acceso: {e}")

if "logged_ip" not in st.session_state and client_ip:
    log_and_notify_access(client_ip, client_user_agent)
    st.session_state.logged_ip = True

# Mostrar IP y navegador
st.markdown(f"**Tu IP pública es:** `{client_ip or 'Obteniendo...'}`")
st.markdown(f"**Navegador:** `{client_user_agent or 'Obteniendo...'}`")

# Escenarios
scenarios = {
    "Lost order": {
        "description": "Customer claims they did not receive their order, even though it's marked as delivered.",
        "steps": [
            "✔️ Greet the customer and validate identity following DPA...",
            "✔️ Open GIPI and verify the order status...",
            "✔️ If marked as 'Delivered', ask if someone else might have received it...",
            "✔️ If customer denies receipt, open BO case using MOCA template...",
            "✔️ Inform the customer that investigation may take up to 72 hours..."
        ],
        "moca_template": "Lost Order"
    },
    "New delivery attempt": {
        "description": "Customer requests a second delivery attempt after the first one failed.",
        "steps": [
            "✔️ Greet the customer and validate identity following DPA...",
            "✔️ Check GIPI for failed delivery attempt...",
            "✔️ Use MOCA template: 'Reschedule Delivery'...",
            "✔️ Confirm new attempt with the customer..."
        ],
        "moca_template": "Reschedule Delivery"
    },
    "Partial delivery": {
        "description": "Customer received only part of the order; some items are missing.",
        "steps": [
            "✔️ Greet the customer and validate identity following DPA...",
            "✔️ Ask the customer which items were missing...",
            "✔️ Check in GIPI if the order was shipped in multiple packages...",
            "✔️ If items are in transit, provide ETA. If not, use MOCA template..."
        ],
        "moca_template": "Missing Items"
    }
}

# Tabs
tab1, tab2, tab3 = st.tabs(["Register Interaction", "History", "Access Logs"])

# TAB 1
with tab1:
    st.title("ZARA - Logistics Transport Prototype")
    selected = st.selectbox("Select reason:", options=list(scenarios.keys()), index=None, placeholder="Choose a scenario...")
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
            st.success("Interaction saved successfully!")

# TAB 2
with tab2:
    st.title("Interaction History")
    docs = list(collection.find().sort("timestamp", -1))
    if not docs:
        st.info("No interactions found yet.")
    else:
        st.dataframe([
            {
                "Date": doc["timestamp"][:19].replace("T", " "),
                "Category": doc["category"],
                "MOCA Template": doc["moca_template"],
                "Notes": doc.get("notes", "")
            } for doc in docs
        ], use_container_width=True)

# TAB 3
with tab3:
    st.title("Access Logs")
    logs = list(db["access_logs"].find().sort("timestamp", -1))
    if not logs:
        st.info("No access logs found.")
    else:
        st.dataframe([
            {
                "Date": log["timestamp"][:19].replace("T", " "),
                "IP": log.get("ip", "N/A"),
                "City": log.get("city", "Unknown"),
                "Country": log.get("country", "Unknown"),
                "User Agent": log.get("user_agent", "Unknown")
            } for log in logs
        ], use_container_width=True)