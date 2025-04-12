import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import requests
import zipfile
import os
import shutil
import tempfile
from sentinelhub import (
    SHConfig, SentinelHubRequest, DataCollection, MimeType, CRS, BBox, Geometry
)
from datetime import datetime
import numpy as np

# Configurar Sentinel Hub (reemplaza con tu clave API)
config = SHConfig()
config.instance_id = "TU_INSTANCE_ID"  # Obtén esto desde Sentinel Hub
config.sh_client_id = "TU_CLIENT_ID"   # Obtén esto desde Sentinel Hub
config.sh_client_secret = "TU_CLIENT_SECRET"  # Obtén esto desde Sentinel Hub

if not config.instance_id:
    print("Por favor, configura tu instance_id, client_id y client_secret de Sentinel Hub.")
    print("Regístrate en https://www.sentinel-hub.com/ para obtenerlos.")
    exit()

# Crear directorio temporal
temp_dir = tempfile.mkdtemp()

# Descargar shapefile de carreteras
url = "http://download.geofabrik.de/north-america/mexico-latest-free.shp.zip"
zip_path = os.path.join(temp_dir, "mexico_shp.zip")

print("Descargando shapefile desde Geofabrik...")
response = requests.get(url, stream=True)
if response.status_code == 200:
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
else:
    print("Error al descargar el shapefile. Código:", response.status_code)
    exit()

# Descomprimir
print("Descomprimiendo shapefile...")
with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

# Buscar capa de carreteras
roads_shp = None
for root, _, files in os.walk(temp_dir):
    for file in files:
        if file == "gis_osm_roads_free_1.shp":
            roads_shp = os.path.join(root, file)
            break
if not roads_shp:
    print("No se encontró gis_osm_roads_free_1.shp.")
    shutil.rmtree(temp_dir)
    exit()

# Crear grafo
G = nx.Graph()

# Nodos con coordenadas (latitud, longitud)
nodes = {
    "Chihuahua": (28.63, -106.08),
    "Torreón": (25.54, -103.41),
    "Ciudad de México": (19.43, -99.13),
    "Puebla": (19.04, -98.21),
    "Guadalajara": (20.67, -103.33),
    "Querétaro": (20.59, -100.39),
}

for node, pos in nodes.items():
    G.add_node(node, pos=pos)

# Aristas con pesos (km, ajustados por terreno)
edges = [
    ("Chihuahua", "Torreón", 450),
    ("Torreón", "Ciudad de México", 800),
    ("Ciudad de México", "Puebla", 130),
    ("Guadalajara", "Querétaro", 350),
    ("Querétaro", "Ciudad de México", 200),
]

for start, end, weight in edges:
    G.add_edge(start, end, weight=weight)

# Calcular rutas
ruta_chihuahua = nx.shortest_path(G, "Chihuahua", "Puebla", weight="weight")
ruta_jalisco = nx.shortest_path(G, "Guadalajara", "Puebla", weight="weight")
print("Ruta desde Chihuahua:", ruta_chihuahua)
print("Ruta desde Jalisco:", ruta_jalisco)

# Cargar carreteras
try:
    roads = gpd.read_file(roads_shp)
    roads = roads[roads["fclass"].isin(["motorway", "trunk", "primary", "secondary"])]
except Exception as e:
    print(f"Error al cargar carreteras: {e}")
    shutil.rmtree(temp_dir)
    exit()

# Descargar imagen satelital con Sentinel Hub
bbox_coords = [-106.5, 18.5, -98.0, 29.0]  # Cubre Chihuahua a Puebla
bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

request = SentinelHubRequest(
    data_folder=temp_dir,
    evalscript="""
        //VERSION=3
        function setup() {
            return {
                input: ["B04", "B03", "B02"],
                output: { bands: 3 }
            };
        }
        function evaluatePixel(sample) {
            return [sample.B04 * 2.5, sample.B03 * 2.5, sample.B02 * 2.5];
        }
    """,
    input_data=[
        SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A,
            time_interval=("2025-01-01", "2025-04-12"),
        )
    ],
    responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
    bbox=bbox,
    size=[1024, 1024],
    config=config,
)

print("Descargando imagen satelital desde Sentinel Hub...")
image = request.get_data(save_data=True)[0]

# Graficar
fig, ax = plt.subplots(figsize=(15, 12))

# Mostrar imagen satelital
extent = [bbox_coords[0], bbox_coords[2], bbox_coords[1], bbox_coords[3]]
ax.imshow(image, extent=extent, alpha=0.8)

# Dibujar carreteras
roads.plot(ax=ax, color="darkgreen", linewidth=0.8, alpha=0.7)

# Añadir nodos
pos = nx.get_node_attributes(G, "pos")
for node, (lat, lon) in pos.items():
    ax.plot(lon, lat, marker="o", color="red", markersize=15, markeredgecolor="black")
    ax.text(lon + 0.2, lat, node, fontsize=10, ha="left", weight="bold", color="black")

# Dibujar rutas
def plot_ruta(ruta, color, label):
    for i in range(len(ruta) - 1):
        start = ruta[i]
        end = ruta[i + 1]
        start_pos = pos[start]
        end_pos = pos[end]
        ax.plot(
            [start_pos[1], end_pos[1]],
            [start_pos[0], end_pos[0]],
            color=color,
            linewidth=4,
            linestyle="--",
            label=label if i == 0 else "",
        )

plot_ruta(ruta_chihuahua, "blue", "Ruta Chihuahua-Puebla")
plot_ruta(ruta_jalisco, "orange", "Ruta Jalisco-Puebla")

# Personalizar
legend_elements = [
    Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markeredgecolor="black", markersize=15, label="Punto Estratégico"),
    Line2D([0], [0], color="blue", lw=4, linestyle="--", label="Ruta Chihuahua-Puebla"),
    Line2D([0], [0], color="orange", lw=4, linestyle="--", label="Ruta Jalisco-Puebla"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=10)
plt.title("Simulación de Guerra Civil con Vigilancia Satelital: Rutas a Puebla", fontsize=16, weight="bold")
plt.xlabel("Longitud", fontsize=12)
plt.ylabel("Latitud", fontsize=12)
plt.grid(True, linestyle="--", alpha=0.3)
plt.tight_layout()

# Guardar mapa
plt.savefig("mapa_satelital_estrategico.png", dpi=300, bbox_inches="tight")
plt.show()

# Limpiar
shutil.rmtree(temp_dir)
print("Directorio temporal limpiado.")