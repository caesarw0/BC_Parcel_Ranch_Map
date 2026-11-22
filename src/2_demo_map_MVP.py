import streamlit as st
import folium
from folium.plugins import GroupedLayerControl
from streamlit_folium import st_folium

# ---------------- STREAMLIT CONFIG ----------------
st.set_page_config(layout="wide")

# ---------------- MAP INIT ----------------
m = folium.Map(
    location=[49.25, -123.1],
    zoom_start=10,
    tiles=None  # REQUIRED for custom basemaps
)

# ---------------- BASE MAPS (RADIO BUTTONS) ----------------
terrain = folium.TileLayer(
    tiles="https://mt0.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
    attr="Google",
    name="Terrain",
    overlay=False,   # 🚨 MUST be False
    control=True
)

satellite = folium.TileLayer(
    tiles="https://mt0.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    attr="Google",
    name="Satellite",
    overlay=False,   # 🚨 MUST be False
    control=True
)

terrain.add_to(m)
satellite.add_to(m)

base_maps = [terrain, satellite]

# ---------------- OVERLAY LAYERS (CHECKBOXES) ----------------
fg_points = folium.FeatureGroup(
    name="Points of Interest",
    overlay=True,
    show=True
)

folium.Marker(
    [49.26, -123.12],
    tooltip="Sample Point"
).add_to(fg_points)

fg_points.add_to(m)

fg_boundary = folium.FeatureGroup(
    name="Boundary",
    overlay=True,
    show=False
)

folium.Circle(
    [49.25, -123.1],
    radius=3000,
    color="green",
    fill=False
).add_to(fg_boundary)

fg_boundary.add_to(m)

# ---------------- GROUPED LAYER CONTROL ----------------
GroupedLayerControl(
    groups={
        "Base Maps": base_maps,
        # "Overlays": [fg_points, fg_boundary],
    },
    collapsed=False,
    position="topright"
).add_to(m)

GroupedLayerControl(
    groups={
        "Overlays": [fg_points, fg_boundary],
    },
    exclusive_groups=False,
    collapsed=False,
    position="topright"
).add_to(m)
# ---------------- DISPLAY ----------------
st_folium(m, width=1200, height=700)
