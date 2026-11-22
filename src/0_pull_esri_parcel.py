import ezesri
import geopandas as gpd
import pandas as pd


for layer_id in range(0, 50):
    print(f"Processing layer {layer_id}")
    # URL for Riverside County, CA parcels layer
    url = f"https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services/ALR_PDF_Map/FeatureServer/{layer_id}"

    # ALR Status: https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services/ALR_PDF_Map/FeatureServer/
    # Cariboord parcels: https://map.cariboord.bc.ca/server/rest/services/Public_Parcels_cityview/FeatureServer/
    # Get layer metadata
    metadata = ezesri.get_metadata(url)
    print("## Layer Metadata Summary")
    print(ezesri.summarize_metadata(metadata))

    # Extract layer to a GeoDataFrame
    print("\n## Extracting Layer to GeoDataFrame")
    df_gdf = ezesri.extract_layer(url)
    print(f"Successfully extracted {len(df_gdf)} features.")
    print(df_gdf.head())

    print(type(df_gdf))
    if len(df_gdf) == 0:
        break
    if isinstance(df_gdf, gpd.GeoDataFrame):
        df_gdf.to_file(f"data/alr_status_layer_{layer_id}.geojson", driver="GeoJSON")
    else:
        df_gdf.to_csv(f"data/alr_status_layer_{layer_id}.csv")
