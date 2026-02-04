import streamlit as st
import folium
import pandas as pd
import geopandas as gpd
from streamlit_folium import st_folium
import branca.colormap as cm

# --- CONFIG ---
st.set_page_config(layout="wide")

# --- DATA LOADING ---
def fix_image_paths_to_static(description):
    if not isinstance(description, str) or 'src="files/' not in description:
        return description

    # Use the absolute web path /static/
    # This points to your local [project_root]/static/ folder
    BASE_IMG_URL = "https://raw.githubusercontent.com/caesarw0/BC_Parcel_Ranch_Map/main/img/"

    fixed_desc = description.replace('src="files/', f'src="{BASE_IMG_URL}')
    
    # Force the image to stay within the popup bounds
    fixed_desc = fixed_desc.replace('<img ', '<img style="width:100%; height:auto;" ')
    
    return fixed_desc

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
        # convert square meters to acres
        gdf['Acres'] = pd.to_numeric(gdf['Shape__Area'], errors='coerce') / 4046.8564224
        
    if 'Four Hearts Package' in gdf.columns:
        gdf['Four Hearts Package'] = gdf['Four Hearts Package'].fillna("N/A").astype(str)
        
    return gdf

@st.cache_data
def load_point_data():
    try:
        gdf = gpd.read_file("data/four_hearts_ranch_kmz_points.geojson").to_crs(epsg=4326)
        return gdf
    except Exception as e:
        st.error(f"Error loading points: {e}")
        return None


try:
    parcels_gdf = load_parcel_data()
    points_gdf = load_point_data()
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


def create_div_icon(icon_url, bg_color="#3498db"):
    # CSS for a circular background with the SVG centered inside
    icon_html = f"""
    <div style="
        background-color: {bg_color};
        width: 30px;
        height: 30px;
        border-radius: 50%;
        border: 2px solid white;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.3);
    ">
        <img src="{icon_url}" style="width: 18px; height: 18px; filter: brightness(0) invert(1);">
    </div>
    """
    return folium.DivIcon(
        html=icon_html,
        icon_size=(30, 30),
        icon_anchor=(15, 15)
    )
# --- MAP RENDERER ---
def create_map(gdf, points_gdf):
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
            'fillOpacity': 0.4 if not is_selected else 0.7
        }

    # Tooltip Fields (Updated Parcel_ID)
    tooltip_fields = [
        "DL#", "Parcel_ID", "Brief description", "Acres", "ALR status", 
        "Assesed Value TOTAL", "BD List Value", "Four Hearts Package"
    ]
    available_tooltips = [f for f in tooltip_fields if f in gdf.columns]

    folium.GeoJson(
        gdf,
        style_function=style_func,
        tooltip=folium.GeoJsonTooltip(fields=available_tooltips, localize=True)
    ).add_to(m)

    for _, row in points_gdf.iterrows():
        # 1. Prepare the HTML Content
        name_html = f"<b>{row['Name']}</b>"
        desc = fix_image_paths_to_static(row.get('Description'))
        
        # Logic: if Description is not None and not empty string
        if pd.notna(desc) and str(desc).strip():
            full_html = f"{name_html}<br>{desc}"
        else:
            full_html = name_html
            
        # 2. Assign Color Logic
        name_lower = row['Name'].lower()
        if "lake" in name_lower and "house" not in name_lower:
            bg = "#229ce6" # Blue for water
        elif "house" in name_lower or "estate" in name_lower:
            bg = "#e74c3c" # Red for residences
        else:
            bg = "#2ecc71" # Green for infrastructure
        
        # 3. Create Marker with Identical Popup and Tooltip
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            icon=create_div_icon(row['map_pin_icon'], bg_color=bg),
            tooltip=folium.Tooltip(full_html) 
        ).add_to(m)
        
    return m

# --- DISPLAY ---
map_output = st_folium(create_map(parcels_gdf, points_gdf), width="100%", height=1000, key="four_hearts_map")

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