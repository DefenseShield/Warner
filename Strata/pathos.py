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
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configurar Sentinel Hub desde .env
config = SHConfig()
config.instance_id = os.getenv("SENTINEL_INSTANCE_ID")
config.sh_client_id = os.getenv("SENTINEL_CLIENT_ID")
config.sh_client_secret = os.getenv("SENTINEL_CLIENT_SECRET")

if not all([config.instance_id, config.sh_client_id, config.sh_client_secret]):
    print("Faltan credenciales de Sentinel Hub en el archivo .env.")
    print("Asegúrate de tener SENTINEL_INSTANCE_ID, SENTINEL_CLIENT_ID y SENTINEL_CLIENT_SECRET.")
    exit()

# Directorio para almacenar shapefiles localmente
shapefile_dir = "data/shapefiles"
os.makedirs(shapefile_dir, exist_ok=True)
roads_shp_path = os.path.join(shapefile_dir, "gis_osm_roads_free_1.shp")

# Verificar si el shapefile ya existe localmente
if not os.path.exists(roads_shp_path):
    # Crear directorio temporal para la descarga
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

    # Buscar capa de carreteras y moverla al directorio local
    roads_shp_temp = None
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if file == "gis_osm_roads_free_1.shp":
                roads_shp_temp = os.path.join(root, file)
                break
    if not roads_shp_temp:
        print("No se encontró gis_osm_roads_free_1.shp.")
        shutil.rmtree(temp_dir)
        exit()

    # Mover archivos necesarios al directorio local
    for ext in [".shp", ".shx", ".dbf", ".prj"]:
        src = roads_shp_temp.replace(".shp", ext)
        dst = os.path.join(shapefile_dir, f"gis_osm_roads_free_1{ext}")
        shutil.move(src, dst)

    # Limpiar directorio temporal
    shutil.rmtree(temp_dir)
    print("Shapefile descargado y guardado localmente.")
else:
    print("Shapefile ya existe localmente, usando la versión guardada.")

# Crear grafo
G = nx.Graph()

# Nodos con coordenadas (latitud, longitud)
nodes = {
    "Chihuahua": (28.63, -106.08),
    "Torreón": (25.54, -103.41),
    "Ciudad de México": (19.43, -99.13),
    "Palacio de Puebla": (19.0433, -98.1981),  # Coordenadas del Palacio Municipal de Puebla
    "Guadalajara": (20.67, -103.33),
    "Querétaro": (20.59, -100.39),
}

for node, pos in nodes.items():
    G.add_node(node, pos=pos)

# Aristas con pesos (km, ajustados por terreno)
edges = [
    ("Chihuahua", "Torreón", 450),
    ("Torreón", "Ciudad de México", 800),
    ("Ciudad de México", "Palacio de Puebla", 130),
    ("Guadalajara", "Querétaro", 350),
    ("Querétaro", "Ciudad de México", 200),
]

for start, end, weight in edges:
    G.add_edge(start, end, weight=weight)

# Calcular rutas
ruta_chihuahua = nx.shortest_path(G, "Chihuahua", "Palacio de Puebla", weight="weight")
ruta_jalisco = nx.shortest_path(G, "Guadalajara", "Palacio de Puebla", weight="weight")
print("Ruta desde Chihuahua:", ruta_chihuahua)
print("Ruta desde Jalisco:", ruta_jalisco)

# Cargar carreteras
try:
    roads = gpd.read_file(roads_shp_path)
    roads = roads[roads["fclass"].isin(["motorway", "trunk", "primary", "secondary"])]
except Exception as e:
    print(f"Error al cargar carreteras: {e}")
    exit()

# Descargar imagen satelital con Sentinel Hub
bbox_coords = [-106.5, 18.5, -98.0, 29.0]  # Cubre Chihuahua a Puebla
bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

request = SentinelHubRequest(
    data_folder="data/sentinel_images",
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
try:
    image = request.get_data(save_data=True)[0]
except Exception as e:
    print(f"Error al descargar la imagen satelital: {e}")
    print("Verifica tu conexión o las credenciales en .env.")
    exit()

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
    # Resaltar el Palacio de Puebla con un marcador diferente
    if node == "Palacio de Puebla":
        ax.plot(lon, lat, marker="*", color="gold", markersize=20, markeredgecolor="black")
    else:
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

plot_ruta(ruta_chihuahua, "blue", "Ruta Chihuahua-Palacio de Puebla")
plot_ruta(ruta_jalisco, "orange", "Ruta Jalisco-Palacio de Puebla")

# Personalizar
legend_elements = [
    Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markeredgecolor="black", markersize=15, label="Punto Estratégico"),
    Line2D([0], [0], marker="*", color="w", markerfacecolor="gold", markeredgecolor="black", markersize=15, label="Palacio de Puebla"),
    Line2D([0], [0], color="blue", lw=4, linestyle="--", label="Ruta Chihuahua-Palacio"),
    Line2D([0], [0], color="orange", lw=4, linestyle="--", label="Ruta Jalisco-Palacio"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=10)
plt.title("Simulación de Guerra Civil con Vigilancia Satelital: Rutas al Palacio de Puebla", fontsize=16, weight="bold")
plt.xlabel("Longitud", fontsize=12)
plt.ylabel("Latitud", fontsize=12)
plt.grid(True, linestyle="--", alpha=0.3)
plt.tight_layout()

# Guardar mapa ("tomar foto")
plt.savefig("mapa_rutas_palacio_puebla_2025.png", dpi=300, bbox_inches="tight")
print("Mapa guardado como 'mapa_rutas_palacio_puebla_2025.png'")
plt.show()