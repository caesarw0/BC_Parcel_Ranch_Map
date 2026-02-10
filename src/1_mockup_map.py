import streamlit as st
import folium
import pandas as pd
import geopandas as gpd
from streamlit_folium import st_folium
import branca.colormap as cm
from branca.element import Element
from folium.plugins import GroupedLayerControl
# --- CONFIG ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
        /* Remove padding from the main Streamlit container */
        .block-container {
            padding: 0rem !important;
            max-width: 100% !important;
        }
        /* Hide the Streamlit header and footer for a cleaner look */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Force the folium container to fill height */
        iframe {
            width: 100vw;
        }
    </style>
""", unsafe_allow_html=True)
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

@st.cache_data
def load_package_data():
    try:
        gdf = gpd.read_file("data/four_hearts_packages.geojson").to_crs(epsg=4326)
        return gdf
    except Exception as e:
        st.error(f"Error loading packages: {e}")
        return None

@st.cache_data
def load_ranch_data():
    try:
        gdf = gpd.read_file("data/four_hearts_ranch_boundary.geojson").to_crs(epsg=4326)
        return gdf
    except Exception as e:
        st.error(f"Error loading ranch: {e}")
        return None

try:
    parcels_gdf = load_parcel_data()
    points_gdf = load_point_data()
    packages_gdf = load_package_data()
    ranch_gdf = load_ranch_data()
except Exception as e:
    st.error(f"Error loading GeoJSON: {e}")
    st.stop()

# --- COLOR MAPPING ---
unique_packages = sorted(parcels_gdf['Four Hearts Package'].unique())
unique_alr =  sorted(parcels_gdf['ALR status'].unique())
colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628']
package_color_map = {pkg: colors[i % len(colors)] for i, pkg in enumerate(unique_packages)}
alr_color_map = {pkg: colors[i % len(colors)] for i, pkg in enumerate(unique_alr)}

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
    # --- INITIAL SETUP ---
    bounds = gdf.total_bounds
    center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]
    
    m = folium.Map(location=center, zoom_start=13, tiles=None)
    
    # 1. Base Maps (TileLayers)
    # We store them in a list for the GroupedLayerControl later
    base_maps = []
    for name, tile_info in GOOGLE_TILES.items():
        tile = folium.TileLayer(
            tiles=tile_info['url'],
            attr=tile_info['attr'],
            name=name,
            overlay=False
        )
        tile.add_to(m)
        base_maps.append(tile)

    # --- STYLING HELPERS ---
    def style_func(feature):
        pkg = feature['properties'].get('Four Hearts Package', "N/A")
        color = package_color_map.get(pkg, '#808080')
        return {'fillColor': color, 'color': 'white', 'weight': 0.5, 'fillOpacity': 0.4}

    tooltip_fields = ["DL#", "Parcel_ID", "Brief description", "Acres", "Four Hearts Package"]
    available_tooltips = [f for f in tooltip_fields if f in gdf.columns]

    # --- CREATE FEATURE GROUPS ---
    # 4. Infrastructure/Points Group
    fg_pins = folium.FeatureGroup(name="Structures", show=True)
    for _, row in points_gdf.iterrows():
        name_html = f"<b>{row['Name']}</b>"
        desc = fix_image_paths_to_static(row.get('Description'))
        full_html = f"{name_html}<br>{desc}" if pd.notna(desc) and str(desc).strip() else name_html
        
        name_lower = row['Name'].lower()
        bg = "#325F82" if "lake" in name_lower and "house" not in name_lower else \
             "#8C985F" if "house" in name_lower or "estate" in name_lower else "#F5D798"
        
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            icon=create_div_icon(row['map_pin_icon'], bg_color=bg),
            tooltip=folium.Tooltip(full_html) 
        ).add_to(fg_pins)
    
    fg_pins.add_to(m)

    # B. Ranch Boundary (Dissolved Polygon)
    fg_boundary = folium.FeatureGroup(name="Ranch Boundary", show=False)
    boundary_gdf = gdf.dissolve() 
    folium.GeoJson(
        boundary_gdf,
        style_function=lambda x: {'fillColor': 'none', 'color': '#2e7d32', 'weight': 3}
    ).add_to(fg_boundary)
    fg_boundary.add_to(m)

    # C. Individual Packages (The Nested List)
    package_layer_list = []
    unlicensed_gdf = gdf[gdf['License'] == False]
    packages = sorted(unlicensed_gdf['Four Hearts Package'].unique())

    for pkg in packages:
        # Note: Name here is just the package name; the plugin handles the 'Parcels' header
        pkg_group = folium.FeatureGroup(name=pkg, show=True)
        pkg_gdf = unlicensed_gdf[unlicensed_gdf['Four Hearts Package'] == pkg]
        
        if not pkg_gdf.empty:
            folium.GeoJson(
                pkg_gdf,
                style_function=style_func,
                tooltip=folium.GeoJsonTooltip(fields=available_tooltips, localize=True)
            ).add_to(pkg_group)
        
        pkg_group.add_to(m)
        package_layer_list.append(pkg_group)

    # D. License/Lease Land
    fg_licensed = folium.FeatureGroup(name="License/Lease Land", show=True)
    licensed_gdf = gdf[gdf['License'] == True]
    if not licensed_gdf.empty:
        folium.GeoJson(licensed_gdf, style_function=style_func).add_to(fg_licensed)
    fg_licensed.add_to(m)

    # --- THE GROUPED LAYER CONTROL (Matches your image) ---
    GroupedLayerControl(
        groups={
            "Base Maps": base_maps,
            "Layers": [fg_pins, fg_boundary],
            "Parcels": package_layer_list,
            "Legal": [fg_licensed]
        },
        exclusive_groups=[], # Set to [base_maps] if you want radio buttons for tiles
        collapsed=False,
        position='topright'
    ).add_to(m)

    # --- CUSTOM CSS FOR INDENTATION ---
    custom_css = """
    <style>
        /* Categorical Header Styling */
        .leaflet-control-layers-group-name {
            font-weight: bold;
            font-size: 14px;
            color: #333;
            margin-top: 10px;
            display: block;
            border-bottom: 1px solid #eee;
        }
        /* Indent the child checkboxes */
        .leaflet-control-layers-group {
            margin-left: 12px;
            padding-left: 5px;
            border-left: 1px solid #ddd;
        }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))
        
    return m

# --- DISPLAY ---
map_output = st_folium(
    create_map(parcels_gdf, points_gdf), 
    width="100%", 
    height=1000, # This will be overridden by the 100vh CSS above
    key="four_hearts_map",
    use_container_width=True
)
