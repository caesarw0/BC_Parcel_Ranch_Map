import streamlit as st
import folium
import pandas as pd
import geopandas as gpd
from streamlit_folium import st_folium
import branca.colormap as cm
from branca.element import Element

# --- CONFIG ---
st.set_page_config(layout="wide")

GOOGLE_TILES = {
    "Terrain Map": {
        "url": "https://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
        "attr": "Terrain"
    },
    "Satellite": {
        "url": "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
        "attr": "Google Hybrid"
    },
}

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
except Exception as e:
    st.error(f"Error loading GeoJSON: {e}")
    st.stop()

# --- COLOR MAPPING ---
unique_packages = sorted(parcels_gdf['Four Hearts Package'].unique())
colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628']
package_color_map = {pkg: colors[i % len(colors)] for i, pkg in enumerate(unique_packages)}

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
    for name, tile_info in GOOGLE_TILES.items():
        folium.TileLayer(
            tiles=tile_info['url'],
            attr=tile_info['attr'],
            name=name,
            overlay=False
        ).add_to(m)

    def style_func(feature):
        # Get the package name from the geojson properties
        pkg = feature['properties'].get('Four Hearts Package', "N/A")
        
        # Look up the color in your package_color_map (defined globally)
        # Default to a neutral gray if the package isn't found
        color = package_color_map.get(pkg, '#808080')
        
        return {
            'fillColor': color,
            'color': 'white',      # Border color
            'weight': 1.5,         # Border thickness
            'fillOpacity': 0.5     # Opacity of the polygon
        }

    # Tooltip Fields (Updated Parcel_ID)
    tooltip_fields = [
        "DL#", "Parcel_ID", "Brief description", "Acres", "ALR status", 
        "Assesed Value TOTAL", "BD List Value", "Four Hearts Package"
    ]
    available_tooltips = [f for f in tooltip_fields if f in gdf.columns]

    # 1. Create FeatureGroups for Licensed vs Unlicensed
    fg_licensed = folium.FeatureGroup(name="License/Lease Land", show=True)
    fg_unlicensed = folium.FeatureGroup(name="Parcels", show=True)

    # 2. Filter GDF into two parts
    licensed_gdf = gdf[gdf['License'] == True]
    unlicensed_gdf = gdf[gdf['License'] == False]

    # Tooltip setup (keep your existing fields)
    available_tooltips = [f for f in tooltip_fields if f in gdf.columns]

    # 3. Add Licensed Parcels to its group
    if not licensed_gdf.empty:
        folium.GeoJson(
            licensed_gdf,
            style_function=style_func,
            tooltip=folium.GeoJsonTooltip(fields=available_tooltips, localize=True)
        ).add_to(fg_licensed)

    # 4. Add Unlicensed Parcels to its group
    if not unlicensed_gdf.empty:
        folium.GeoJson(
            unlicensed_gdf,
            style_function=style_func,
            tooltip=folium.GeoJsonTooltip(fields=available_tooltips, localize=True)
        ).add_to(fg_unlicensed)

    # Add both groups to the map
    fg_licensed.add_to(m)
    fg_unlicensed.add_to(m)

    fg_pins = folium.FeatureGroup(name="Structures", show=True)

    for _, row in points_gdf.iterrows():
        name_html = f"<b>{row['Name']}</b>"
        desc = fix_image_paths_to_static(row.get('Description'))
        full_html = f"{name_html}<br>{desc}" if pd.notna(desc) and str(desc).strip() else name_html
        
        # Color logic
        name_lower = row['Name'].lower()
        bg = "#325F82" if "lake" in name_lower and "house" not in name_lower else \
             "#8C985F" if "house" in name_lower or "estate" in name_lower else "#F5D798"
        
        # Add marker to the FEATURE GROUP instead of the map directly
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            icon=create_div_icon(row['map_pin_icon'], bg_color=bg),
            tooltip=folium.Tooltip(full_html) 
        ).add_to(fg_pins)
    
    # Add the group to the map
    fg_pins.add_to(m)

    # 4. Add the Toggle Control (Top Right)
    folium.LayerControl(position='topright', collapsed=False).add_to(m)

    # Define the CSS targeting the specific classes in your HTML
    custom_css = """
    <style>
        /* Targets the specific selector class from your HTML */
        .leaflet-control-layers-selector {
            accent-color: #2e7d32 !important; /* A nice forest green */
            cursor: pointer;
        }

        /* Adds a little breathing room between the list items */
        .leaflet-control-layers-list label {
            margin-bottom: 5px;
            display: block;
        }
    </style>
    """

    # Inject the style into the map header
    m.get_root().header.add_child(Element(custom_css))
        
    return m

# --- DISPLAY ---
map_output = st_folium(create_map(parcels_gdf, points_gdf), width="100%", height=1000, key="four_hearts_map")
