import streamlit as st
import hashlib
import streamlit.components.v1 as components
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import pytz
import requests

# --- PROTECCIÓN POR CONTRASEÑA ---
def cifrar(texto):
    return hashlib.sha256(texto.encode()).hexdigest()

CLAVE_VALIDA = "63e92773ea84a0e2bc896c7117dfc7a9ffbe3c42a5d02153a35d65eae1589de6"

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.set_page_config(page_title="ZARA - Login", layout="centered")
    st.title("🔐 Acceso restringido")
    clave = st.text_input("Ingresa la clave:", type="password")
    if st.button("Entrar"):
        if cifrar(clave) == CLAVE_VALIDA:
            st.session_state.autenticado = True
            st.experimental_rerun()
        else:
            st.error("❌ Clave incorrecta")
    st.stop()

# --- CONFIGURACIÓN APP ---
load_dotenv()
st.set_page_config(page_title="ZARA - Logistics Prototype", layout="centered")
tz = pytz.timezone("America/Bogota")

# MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["zara_db"]
collection = db["logistics_interactions"]
access_logs = db["access_logs"]

# Obtener IP pública
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

# Leer cookie con streamlit_javascript
try:
    import streamlit_javascript as stj
    cookie_js = stj.st_javascript("document.cookie")
    client_ip = cookie_js.split("client_ip=")[-1].split(";")[0] if "client_ip=" in cookie_js else None
except Exception:
    client_ip = None

# Registro acceso
def log_access(ip):
    try:
        ip_data = requests.get(f"https://ipinfo.io/{ip}/json").json() if ip else {}
        city = ip_data.get("city", "Unknown")
        country = ip_data.get("country", "Unknown")

        # Telegram
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if telegram_token and telegram_chat_id:
            msg = f"⚠️ Nueva visita\nIP: {ip or 'N/A'}\nUbicación: {city}, {country}"
            requests.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                data={"chat_id": telegram_chat_id, "text": msg}
            )

        # Mongo
        access_logs.insert_one({
            "timestamp": datetime.now(tz).isoformat(),
            "ip": ip or "N/A",
            "city": city,
            "country": country
        })
    except Exception as e:
        st.error(f"Error al registrar acceso: {e}")

if "logged_ip" not in st.session_state and client_ip:
    log_access(client_ip)
    st.session_state.logged_ip = True

st.markdown(f"**Tu IP pública es:** `{client_ip or 'Obteniendo...'}`")

# Escenarios
scenarios = {
    "Lost order": {
        "description": "Customer claims they did not receive their order, even though it's marked as delivered.",
        "steps": [
            "✔️ Validate customer identity...",
            "✔️ Verify order status in GIPI...",
            "✔️ Ask if someone else received it...",
            "✔️ Open BO case using MOCA template...",
            "✔️ Inform about 72h investigation time..."
        ],
        "moca_template": "Lost Order"
    },
    "New delivery attempt": {
        "description": "Customer requests a second delivery attempt.",
        "steps": [
            "✔️ Validate customer identity...",
            "✔️ Check failed delivery in GIPI...",
            "✔️ Use MOCA template: Reschedule Delivery...",
            "✔️ Confirm new attempt with customer..."
        ],
        "moca_template": "Reschedule Delivery"
    },
    "Partial delivery": {
        "description": "Customer received only part of the order.",
        "steps": [
            "✔️ Validate customer identity...",
            "✔️ Identify missing items...",
            "✔️ Check if shipped separately...",
            "✔️ Provide ETA or escalate with MOCA..."
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
            st.success("Interaction saved!")

# TAB 2
with tab2:
    st.title("Interaction History")
    docs = list(collection.find().sort("timestamp", -1))
    if not docs:
        st.info("No interactions found.")
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
    logs = list(access_logs.find().sort("timestamp", -1))
    if not logs:
        st.info("No access logs found.")
    else:
        st.dataframe([
            {
                "N°": i + 1,
                "Date": log["timestamp"][:19].replace("T", " "),
                "IP": log["ip"],
                "City": log["city"],
                "Country": log["country"]
            } for i, log in enumerate(logs)
        ], use_container_width=True)
