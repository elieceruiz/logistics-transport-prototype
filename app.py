import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import pytz
import requests

# Cargar variables de entorno
load_dotenv()
tz = pytz.timezone("America/Bogota")

# Configuración de página
st.set_page_config(page_title="ZARA - Logistics Prototype", layout="centered")

# Conexión Mongo
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["zara_db"]
collection = db["logistics_interactions"]

# JavaScript para obtener la IP
components.html("""
<script>
if (!document.cookie.includes("client_ip")) {
    fetch("https://api.ipify.org?format=json")
    .then(response => response.json())
    .then(data => {
        document.cookie = "client_ip=" + data.ip + "; path=/";
        location.reload();
    });
}
</script>
""", height=0)

# Obtener IP desde cookie
try:
    import streamlit_javascript as stj
    cookie_js = stj.st_javascript("document.cookie")
    client_ip = cookie_js.split("client_ip=")[-1].split(";")[0] if "client_ip=" in cookie_js else None
except Exception:
    client_ip = None

# Función para detectar navegador
def get_browser_name(ua):
    if not ua:
        return "Unknown"
    ua = ua.lower()
    if "vivaldi" in ua:
        return "Vivaldi"
    elif "edg" in ua:
        return "Edge"
    elif "opr" in ua or "opera" in ua:
        return "Opera"
    elif "brave" in ua:
        return "Brave"
    elif "chrome" in ua and "chromium" not in ua:
        return "Chrome"
    elif "firefox" in ua:
        return "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        return "Safari"
    else:
        return "Other"

# Registrar acceso
def log_and_notify_access(ip):
    try:
        ua = stj.st_javascript("navigator.userAgent")
        browser = get_browser_name(ua)
        ip_data = requests.get(f"https://ipinfo.io/{ip}/json").json() if ip else {}
        city = ip_data.get("city", "Unknown")
        country = ip_data.get("country", "Unknown")

        # Telegram
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if telegram_token and telegram_chat_id:
            message = f"⚠️ Nueva visita\nIP: {ip or 'N/A'}\nUbicación: {city}, {country}\nNavegador: {browser}"
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            requests.post(url, data={"chat_id": telegram_chat_id, "text": message})

        # Mongo log
        db["access_logs"].insert_one({
            "timestamp": datetime.now(tz).isoformat(),
            "ip": ip or "N/A",
            "city": city,
            "country": country,
            "user_agent": ua,
            "browser": browser
        })

    except Exception as e:
        st.error(f"Error registrando acceso: {e}")

if "logged_ip" not in st.session_state and client_ip:
    log_and_notify_access(client_ip)
    st.session_state.logged_ip = True

# Mostrar IP al usuario
st.markdown(f"**Tu IP pública es:** `{client_ip or 'Obteniendo...'}`")

# Escenarios de ejemplo
scenarios = {
    "Lost order": {
        "description": "Customer claims they did not receive their order.",
        "steps": [
            "✔️ Validate identity",
            "✔️ Check GIPI delivery status",
            "✔️ Ask if someone else received it",
            "✔️ Open BO case",
            "✔️ Inform about 72h investigation"
        ],
        "moca_template": "Lost Order"
    },
    "New delivery attempt": {
        "description": "Customer requests a second delivery attempt.",
        "steps": [
            "✔️ Validate identity",
            "✔️ Check failed delivery attempt",
            "✔️ Use MOCA: Reschedule Delivery",
            "✔️ Confirm new attempt"
        ],
        "moca_template": "Reschedule Delivery"
    },
    "Partial delivery": {
        "description": "Customer received only part of the order.",
        "steps": [
            "✔️ Validate identity",
            "✔️ Ask for missing items",
            "✔️ Check if sent in multiple packages",
            "✔️ Provide ETA or open MOCA"
        ],
        "moca_template": "Missing Items"
    }
}

# Tabs
tab1, tab2, tab3 = st.tabs(["Register Interaction", "History", "Access Logs"])

# TAB 1
with tab1:
    st.title("ZARA - Logistics Transport Prototype")
    selected = st.selectbox("Select reason:", list(scenarios.keys()), index=None, placeholder="Choose scenario...")
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

# TAB 2 - Historial
with tab2:
    st.title("Interaction History")
    docs = list(collection.find().sort("timestamp", -1))
    if not docs:
        st.info("No interactions found.")
    else:
        st.dataframe([{
            "Date": doc["timestamp"][:19].replace("T", " "),
            "Category": doc["category"],
            "MOCA Template": doc["moca_template"],
            "Notes": doc.get("notes", "")
        } for doc in docs])

# TAB 3 - Access logs
with tab3:
    st.title("Access Logs")
    logs = list(db["access_logs"].find().sort("timestamp", -1))
    if not logs:
        st.info("No access logs found.")
    else:
        st.dataframe([{
            "Date": log["timestamp"][:19].replace("T", " "),
            "IP": log["ip"],
            "City": log["city"],
            "Country": log["country"],
            "Browser": log["browser"]
        } for log in logs])