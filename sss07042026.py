import streamlit as st
import pandas as pd
import plotly.express as px
import os
import zipfile
import pydeck as pdk

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="SSS Dashboard", layout="wide")

# ---------------------------
# THEME
# ---------------------------
theme = st.toggle("Dark Mode")

bg_color = "#0e1117" if theme else "white"
text_color = "white" if theme else "black"

# ---------------------------
# STYLE
# ---------------------------
def style_chart(fig):
    fig.update_layout(
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font_color=text_color
    )
    return fig

# ---------------------------
# TITLE
# ---------------------------
st.markdown("## 🚢 SSS DATA ANALYTICS DASHBOARD")

# ---------------------------
# LOAD DATA
# ---------------------------
@st.cache_data
def load_data():
    zip_files = [f for f in os.listdir() if f.endswith(".zip")]

    if not zip_files:
        st.error("❌ No ZIP file found")
        st.stop()

    with zipfile.ZipFile(zip_files[0]) as z:
        csv_files = [f for f in z.namelist() if f.endswith(".csv")]

        if not csv_files:
            st.error("❌ No CSV inside ZIP")
            st.stop()

        with z.open(csv_files[0]) as f:
            df = pd.read_csv(f, encoding="cp1252")

    return df

df = load_data()

# ---------------------------
# CLEAN DATA
# ---------------------------
df = df.fillna("")

df["Operator_Code"] = df["Operator_Code"].astype(str).str.strip()
df["Service"] = df["Service"].astype(str).str.strip()
df["From_Port"] = df["From_Port"].astype(str).str.strip().str.upper()
df["To_Port"] = df["To_Port"].astype(str).str.strip().str.upper()

df["Inserted_At"] = pd.to_datetime(df["Inserted_At"], errors="coerce", dayfirst=True)
df["Inserted_Date"] = df["Inserted_At"].dt.normalize()

# ---------------------------
# FILTERS
# ---------------------------
st.markdown("### 🔍 Filters")

col1, col2, col3, col4 = st.columns(4)

operator = col1.multiselect("Operator", sorted(df["Operator_Code"].unique()))
service = col2.multiselect("Service", sorted(df["Service"].unique()))
from_port = col3.multiselect("From Port", sorted(df["From_Port"].unique()))
to_port = col4.multiselect("To Port", sorted(df["To_Port"].unique()))

filtered_df = df.copy()

if operator:
    filtered_df = filtered_df[filtered_df["Operator_Code"].isin(operator)]
if service:
    filtered_df = filtered_df[filtered_df["Service"].isin(service)]
if from_port:
    filtered_df = filtered_df[filtered_df["From_Port"].isin(from_port)]
if to_port:
    filtered_df = filtered_df[filtered_df["To_Port"].isin(to_port)]

# ---------------------------
# KPIs
# ---------------------------
k1, k2, k3, k4 = st.columns(4)

k1.metric("Total Records", len(filtered_df))
k2.metric("Operators", filtered_df["Operator_Code"].nunique())
k3.metric("Routes", filtered_df["From_Port"].nunique())
k4.metric("Services", filtered_df["Service"].nunique())

# ---------------------------
# SUMMARY TABLE
# ---------------------------
st.markdown("### 📊 Date vs Operator Summary")

summary_df = (
    filtered_df.groupby(["Inserted_Date", "Operator_Code"])
    .size()
    .reset_index(name="Count")
)

summary_df["Inserted_Date"] = summary_df["Inserted_Date"].dt.strftime("%d-%m-%Y")

total = pd.DataFrame({
    "Inserted_Date": ["TOTAL"],
    "Operator_Code": [""],
    "Count": [summary_df["Count"].sum()]
})

final_df = pd.concat([summary_df, total])
st.dataframe(final_df, use_container_width=True)

# ---------------------------
# OPERATOR TREND
# ---------------------------
st.markdown("### 📈 Operator Count")

trend = filtered_df["Operator_Code"].value_counts().reset_index()
trend.columns = ["Operator", "Count"]

fig = px.bar(trend, x="Operator", y="Count", text="Count")
fig.update_traces(textposition="outside")
st.plotly_chart(style_chart(fig), use_container_width=True)

# ---------------------------
# TOP ROUTES
# ---------------------------
st.markdown("### 🌍 Top Routes")

route_df = (
    filtered_df.groupby(["From_Port", "To_Port"])
    .size()
    .reset_index(name="Count")
)

route_df["Route"] = route_df["From_Port"] + " → " + route_df["To_Port"]
route_df = route_df.sort_values(by="Count", ascending=False).head(10)

fig_route = px.bar(route_df, x="Count", y="Route", orientation="h", text="Count")
st.plotly_chart(style_chart(fig_route), use_container_width=True)

# ---------------------------
# SERVICE DISTRIBUTION
# ---------------------------
st.markdown("### 📦 Service Distribution")

service_df = filtered_df["Service"].value_counts().reset_index()
service_df.columns = ["Service", "Count"]

fig_service = px.bar(service_df.head(10), x="Count", y="Service", orientation="h", text="Count")
st.plotly_chart(style_chart(fig_service), use_container_width=True)

# ---------------------------
# MAP
# ---------------------------
st.markdown("### 🗺️ Route Map")

try:
    country_df = pd.read_csv("country_lat_lon.csv")

    country_df.columns = ["Country_Code", "Latitude", "Longitude"]
    country_df["Country_Code"] = country_df["Country_Code"].astype(str).str.upper()

    map_df = filtered_df.copy()
    map_df["From_Country"] = map_df["From_Port_Code"].astype(str).str[:2]
    map_df["To_Country"] = map_df["To_Port_Code"].astype(str).str[:2]

    route_df = (
        map_df.groupby(["From_Country", "To_Country"])
        .size()
        .reset_index(name="Count")
    )

    route_df = route_df.merge(
        country_df, left_on="From_Country", right_on="Country_Code", how="left"
    ).rename(columns={"Latitude": "from_lat", "Longitude": "from_lon"})

    route_df = route_df.merge(
        country_df, left_on="To_Country", right_on="Country_Code", how="left"
    ).rename(columns={"Latitude": "to_lat", "Longitude": "to_lon"})

    route_df = route_df.dropna()

    if not route_df.empty:
        layer = pdk.Layer(
            "ArcLayer",
            data=route_df,
            get_source_position=["from_lon", "from_lat"],
            get_target_position=["to_lon", "to_lat"],
            get_width=2,
            get_source_color=[0, 150, 255],
            get_target_color=[255, 100, 150],
        )

        view = pdk.ViewState(latitude=20, longitude=0, zoom=1)

        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view))

except:
    st.warning("Map data not available")
