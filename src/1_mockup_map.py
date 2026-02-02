import streamlit as st
import folium
import pandas as pd
import geopandas as gpd
from streamlit_folium import st_folium
import branca.colormap as cm

# --- CONFIG ---
st.set_page_config(layout="wide")

# --- DATA LOADING ---
@st.cache_data
def load_parcel_data():
    gdf = gpd.read_file("data/four_hearts_parcels_with_price.geojson").to_crs(epsg=4326)

    # --- RENAME Designation3 TO PID ---
    if 'Designation3' in gdf.columns:
        gdf = gdf.rename(columns={'Designation3': 'Parcel_ID'})

    price_cols = ['Assesed Value Land', 'Assesed Value Improve', 'Assesed Value TOTAL', 
                  'BD List Value', 'Estimated property transfer tax ()',
                  'Estimated PTT (cultivated farmland)', 'Estimated PTT (rangeland)']

    for col in price_cols:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col].astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce').round(2)
    
    if 'Acres' in gdf.columns:
        gdf['Acres'] = pd.to_numeric(gdf['Acres'], errors='coerce').round(2)
        
    if 'Four Hearts Package' in gdf.columns:
        gdf['Four Hearts Package'] = gdf['Four Hearts Package'].fillna("N/A").astype(str)
        
    return gdf

try:
    parcels_gdf = load_parcel_data()
    # Use the new PID name for filtering
    selectable_gdf = parcels_gdf[parcels_gdf['Parcel_ID'].notna()].copy()
except Exception as e:
    st.error(f"Error loading GeoJSON: {e}")
    st.stop()

# --- COLOR MAPPING ---
unique_packages = sorted(parcels_gdf['Four Hearts Package'].unique())
colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628']
package_color_map = {pkg: colors[i % len(colors)] for i, pkg in enumerate(unique_packages)}

# --- SESSION STATE ---
if 'selected_id' not in st.session_state:
    st.session_state.selected_id = None

# --- MAP RENDERER ---
def create_map(gdf):
    bounds = gdf.total_bounds
    center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]
    
    m = folium.Map(location=center, zoom_start=13, tiles=None)
    google_hybrid_url = 'https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}'
    folium.TileLayer(tiles=google_hybrid_url, attr='Google', name='Google Hybrid', overlay=False).add_to(m)

    def style_func(feature):
        pkg = feature['properties'].get('Four Hearts Package', "N/A")
        pid = feature['properties'].get('Parcel_ID') # Updated to Parcel_ID
        
        base_color = package_color_map.get(pkg, '#3498db')
        is_selected = (pid == st.session_state.selected_id and st.session_state.selected_id is not None)
        
        return {
            'fillColor': '#ffff00' if is_selected else base_color,
            'color': 'white' if not is_selected else 'black',
            'weight': 1.5 if not is_selected else 3,
            'fillOpacity': 0.6 if not is_selected else 0.9
        }

    # Tooltip Fields (Updated Parcel_ID)
    tooltip_fields = [
        "Parcel_ID", "Brief description", "Acres", "ALR status", 
        "Assesed Value TOTAL", "BD List Value", "Four Hearts Package"
    ]
    available_tooltips = [f for f in tooltip_fields if f in gdf.columns]

    folium.GeoJson(
        gdf,
        style_function=style_func,
        tooltip=folium.GeoJsonTooltip(fields=available_tooltips, localize=True)
    ).add_to(m)
    
    return m

# --- DISPLAY ---
map_output = st_folium(create_map(parcels_gdf), width="100%", height=600, key="four_hearts_map")

# Metrics
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.metric("Total Parcels", len(parcels_gdf))
with m_col2:
    avg_val = parcels_gdf['Assesed Value TOTAL'].mean(skipna=True) if 'Assesed Value TOTAL' in parcels_gdf.columns else 0
    st.metric("Avg Assessed Value", f"${avg_val:,.0f}")
with m_col3:
    st.metric("Currently Selected PID", st.session_state.selected_id if st.session_state.selected_id else "None")

# Table (Updated to PID)
st.write("### Property Financial Overview")
event = st.dataframe(
    selectable_gdf[["PID", "Four Hearts Package", "Acres", "Assesed Value TOTAL", "BD List Value"]],
    use_container_width=True,
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun"
)

# SYNC LOGIC
if map_output and map_output.get("last_active_drawing"):
    new_id = map_output["last_active_drawing"]["properties"].get("PID") # Updated to PID
    if new_id and new_id != st.session_state.selected_id:
        st.session_state.selected_id = new_id
        st.rerun()

if event.selection.rows:
    selected_row_index = event.selection.rows[0]
    new_id = selectable_gdf.iloc[selected_row_index]['PID'] # Updated to PID
    if new_id != st.session_state.selected_id:
        st.session_state.selected_id = new_id
        st.rerun()