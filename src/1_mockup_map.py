import streamlit as st
import folium
import pandas as pd
import geopandas as gpd
from streamlit_folium import st_folium

# --- CONFIG & STYLING ---
st.set_page_config(layout="wide", page_title="Cariboo Parcel Explorer")

# --- DATA LOADING ---
@st.cache_data
def load_parcel_data():
    # Load your specific Cariboo GeoJSON
    gdf = gpd.read_file("data/cariboord_filtered_parcels.geojson").to_crs(epsg=4326)
    
    # Ensure standard BC parcel columns exist or create defaults
    # Common BC fields: PID, FOLIO, LEGAL_DESCRIPTION, ADDRESS, Shape__Area
    if 'Shape__Area' in gdf.columns:
        gdf['ACRES'] = (gdf['Shape__Area'] * 0.000247105).round(2)
    return gdf

try:
    parcels_gdf = load_parcel_data()
except Exception as e:
    st.error(f"Error loading Cariboo GeoJSON: {e}")
    st.stop()

# --- SESSION STATE ---
if 'selected_pid' not in st.session_state:
    st.session_state.selected_pid = None

# --- HEADER ---
st.title("🌲 Cariboo Regional District Parcel Viewer")
st.markdown("Consulting Dashboard: Spatial Property Analysis")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Properties")
unique_plans = sorted(parcels_gdf['GlobalID'].unique()) if 'GlobalID' in parcels_gdf.columns else []
selected_plan = st.sidebar.selectbox("Filter by Plan Number", ["All"] + unique_plans)

filtered_df = parcels_gdf.copy()
if selected_plan != "All":
    filtered_df = filtered_df[filtered_df['GlobalID'] == selected_plan]

# --- METRICS ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Parcels", len(filtered_df))
with col2:
    avg_size = filtered_df['ACRES'].mean() if 'ACRES' in filtered_df.columns else 0
    st.metric("Avg Parcel Size", f"{avg_size:.2f} Acres")
with col3:
    st.metric("Region", "Cariboo, BC")

# --- MAP RENDERER ---
def create_map(gdf):
    # Center map on the data
    bounds = gdf.total_bounds
    center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]
    
    m = folium.Map(location=center, zoom_start=13, tiles=None)

    # Apply your Google Satellite Tiles
    google_sat_url = 'https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}'
    folium.TileLayer(
        tiles=google_sat_url,
        attr='Google Satellite',
        name='Satellite',
        overlay=False
    ).add_to(m)

    # Style function for parcels
    style_func = lambda x: {
        'fillColor': '#ffff00' if x['properties'].get('GlobalID') == st.session_state.selected_pid else '#3498db',
        'color': 'white',
        'weight': 1,
        'fillOpacity': 0.4
    }

    # Add Parcel GeoJSON
    folium.GeoJson(
        gdf,
        style_function=style_func,
        tooltip=folium.GeoJsonTooltip(
            fields=['GlobalID'] if 'GlobalID' in gdf.columns else gdf.columns[:3].tolist(),
            aliases=['GlobalID:'],
            localize=True
        )
    ).add_to(m)
    
    return m

# --- DISPLAY MAP & TABLE ---
map_col, table_col = st.columns([2, 1])

with map_col:
    m = create_map(filtered_df)
    map_output = st_folium(m, width="100%", height=600, key="cariboo_map")

with table_col:
    st.subheader("Property List")
    # Interactive Table
    event = st.dataframe(
        filtered_df[['GlobalID','ACRES']].drop(columns='geometry', errors='ignore'),
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )

# --- CLICK LOGIC ---
if map_output and map_output.get("last_active_drawing"):
    new_pid = map_output["last_active_drawing"]["properties"].get("GlobalID")
    if new_pid != st.session_state.selected_pid:
        st.session_state.selected_pid = new_pid
        st.rerun()

if event.selection.rows:
    selected_row_index = event.selection.rows[0]
    st.session_state.selected_pid = filtered_df.iloc[selected_row_index]['GlobalID']
    st.info(f"Selected PID: {st.session_state.selected_pid}")