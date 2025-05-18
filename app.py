
"""
Aplicación Streamlit 100% en Python para mostrar y actualizar en tiempo real la ruta
óptima entre San José Xacxamayo y la Presa Valsequillo.
"""
import os
import streamlit as st #aplicacion de uso libre para poder realizar el analisis
import numpy as np
import geopandas as gpd
import rasterio
import networkx as nx
from shapely.geometry import Point, LineString
from rasterio.transform import from_origin
from pyproj import Transformer
from streamlit_folium import folium_static
import folium

st.set_page_config(page_title="Agua Viva SJX", layout="wide")
st.title("Ruta Hidráulica en San José Xacxamayo")

# --- Coordenadas fijas ---
# Presa Valsequillo (aprox.)
origin = Point(-98.1475, 19.0165)
# San José Xacxamayo (aprox.)
destiny = Point(-98.1780, 19.0410)

# --- Crear raster sintético (DEM + suelo) para la zona ---
if not os.path.exists('dem_sjx.tif') or not os.path.exists('suelo_sjx.tif'):
    st.info("Generando DEM y suelo sintéticos para la zona SJX...")
    width, height = 200, 200
    cell_size = 0.0005  # tamaño en grados (~50 m)
    ulx = destiny.x - cell_size * width / 2
    uly = destiny.y + cell_size * height / 2
    transform = from_origin(ulx, uly, cell_size, cell_size)
    rng = np.random.RandomState(0)
    dem = 100 + 20 * np.sin(np.linspace(0, 3 * np.pi, width))[None, :] + rng.normal(0, 1, (height, width))
    soil = rng.randint(1, 5, size=(height, width))
    for data, name in [(dem, 'dem_sjx.tif'), (soil, 'suelo_sjx.tif')]:
        with rasterio.open(
            name, 'w', driver='GTiff', height=height, width=width,
            count=1, dtype=data.dtype, crs='EPSG:4326', transform=transform
        ) as dst:
            dst.write(data, 1)

# --- Cálculo de ruta óptima ---
st.info("Calculando ruta óptima...")
dem_ds = rasterio.open('dem_sjx.tif')
soil_ds = rasterio.open('suelo_sjx.tif')
dem = dem_ds.read(1)
soil = soil_ds.read(1)
affine = dem_ds.transform
crs = dem_ds.crs
orig_px = dem_ds.index(origin.x, origin.y)
dest_px = dem_ds.index(destiny.x, destiny.y)
rows, cols = dem.shape
G = nx.grid_2d_graph(rows, cols, create_using=nx.DiGraph)
for (i, j) in G.nodes():
    elev = dem[i, j]
    slope = abs(dem[i, j + 1] - elev) if j + 1 < cols else 0
    soil_val = soil[i, j]
    w = 1 + slope / 5 + soil_val * 0.2
    G.nodes[(i, j)]['weight'] = w
for u, v in G.edges():
    G.edges[u, v]['weight'] = (G.nodes[u]['weight'] + G.nodes[v]['weight']) / 2
path = nx.dijkstra_path(G, source=orig_px, target=dest_px, weight='weight')
if st.button("🔄 Actualizar ruta"):
    path = nx.dijkstra_path(G, source=orig_px, target=dest_px, weight='weight')

# --- Convertir ruta a coordenadas geográficas ---
transformer = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
coords = []
for i, j in path:
    x, y = affine * (j + 0.5, i + 0.5)
    lon, lat = transformer.transform(x, y)
    coords.append((lat, lon))  # folium usa [lat, lon]

# --- Mostrar mapa con folium ---
m = folium.Map(location=[destiny.y, destiny.x], zoom_start=13)
# marcadores
folium.Marker([origin.y, origin.x], tooltip="Presa Valsequillo", icon=folium.Icon(color='blue')).add_to(m)
folium.Marker([destiny.y, destiny.x], tooltip="San José Xacxamayo", icon=folium.Icon(color='green')).add_to(m)
# línea de ruta
folium.PolyLine(coords, color='red', weight=4, opacity=0.7).add_to(m)
folium_static(m)

st.markdown("---")
st.write("**Distancia estimada (nodos):**", len(path))
st.write("**Altura mínima (m):**", float(np.min(dem)))
st.write("**Altura máxima (m):**", float(np.max(dem)))

# Instrucciones:
# pip install streamlit geopandas rasterio networkx shapely pyproj streamlit-folium
# Ejecutar: streamlit run app.py
