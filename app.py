import streamlit as st
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import pytz

# Configuración inicial
st.set_page_config(page_title="ZARA – Logistics Prototype", layout="centered")

# Zona horaria de Bogotá
tz = pytz.timezone("America/Bogota")

# Cargar URI de entorno
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://elieceruiz_admin:fPydI3B73ijAukEz@cluster0.rqzim65.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Conexión MongoDB
client = MongoClient(MONGO_URI)
db = client["zara_db"]
collection = db["logistics_interactions"]

# Definir escenarios
scenarios = {
    "Lost order": {
        "description": "Customer claims they did not receive their order, even though it's marked as delivered.",
        "steps": [
            "✔️ Greet the customer and validate identity following DPA: collect at least 3 of the following — order number, email, associated phone, full name.",
            "✔️ Open GIPI and verify the order status.",
            "✔️ If marked as 'Delivered', ask if someone else might have received it.",
            "✔️ If customer denies receipt, open BO case using MOCA template: 'Lost Order'.",
            "✔️ Inform the customer that investigation may take up to 72 hours and they will be contacted by logistics."
        ],
        "moca_template": "Lost Order"
    },
    "New delivery attempt": {
        "description": "Customer requests a second delivery attempt after the first one failed.",
        "steps": [
            "✔️ Greet the customer and validate identity following DPA: collect at least 3 of the following — order number, email, associated phone, full name.",
            "✔️ Check GIPI for failed delivery attempt.",
            "✔️ Use MOCA template: 'Reschedule Delivery' to document request.",
            "✔️ Confirm new attempt with the customer and share the estimated delivery date."
        ],
        "moca_template": "Reschedule Delivery"
    },
    "Partial delivery": {
        "description": "Customer received only part of the order; some items are missing.",
        "steps": [
            "✔️ Greet the customer and validate identity following DPA: collect at least 3 of the following — order number, email, associated phone, full name.",
            "✔️ Ask the customer which items were missing.",
            "✔️ Check in GIPI if the order was shipped in multiple packages.",
            "✔️ If items are in transit, provide ETA. If not, use MOCA template: 'Missing Items'."
        ],
        "moca_template": "Missing Items"
    }
}

# Tabs
tab1, tab2 = st.tabs(["Register Interaction", "History"])

# TAB 1 – Registro
with tab1:
    st.title("ZARA – Logistics Transport Prototype")
    st.markdown("Select a scenario and follow the guided checklist.")

    selected = st.selectbox("Select reason:", list(scenarios.keys()))

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

# TAB 2 – Historial
with tab2:
    st.title("Interaction History")
    docs = list(collection.find().sort("timestamp", -1))

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