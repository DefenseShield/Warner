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

# Cargar carreteras
try:
    roads = gpd.read_file(roads_shp_path)
    roads = roads[roads["fclass"].isin(["motorway", "trunk", "primary", "secondary", "tertiary"])]
except Exception as e:
    print(f"Error al cargar carreteras: {e}")
    exit()

# Definir el área alrededor del Palacio Municipal de Puebla
palacio_coords = (19.0433, -98.1981)  # Latitud, Longitud
# Bounding box: ~1 km x 1 km alrededor del Palacio
delta = 0.009  # Aproximadamente 1 km en grados (1 grado ~ 111 km)
bbox_coords = [
    palacio_coords[1] - delta,  # Longitud mínima
    palacio_coords[0] - delta,  # Latitud mínima
    palacio_coords[1] + delta,  # Longitud máxima
    palacio_coords[0] + delta   # Latitud máxima
]
bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

# Filtrar carreteras dentro del bounding box
roads = roads.cx[bbox_coords[0]:bbox_coords[2], bbox_coords[1]:bbox_coords[3]]

# Descargar imagen satelital con Sentinel Hub (alta resolución)
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
    size=[2048, 2048],  # Alta resolución
    config=config,
)

print("Descargando imagen satelital de alta resolución desde Sentinel Hub...")
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
ax.imshow(image, extent=extent, alpha=0.9)

# Dibujar carreteras locales
roads.plot(ax=ax, color="darkgreen", linewidth=1.5, alpha=0.7)

# Añadir el marcador del Palacio
ax.plot(palacio_coords[1], palacio_coords[0], marker="*", color="gold", markersize=25, markeredgecolor="black")
ax.text(palacio_coords[1] + 0.001, palacio_coords[0], "Palacio de Puebla", fontsize=12, ha="left", weight="bold", color="black")

# Personalizar
legend_elements = [
    Line2D([0], [0], marker="*", color="w", markerfacecolor="gold", markeredgecolor="black", markersize=15, label="Palacio de Puebla"),
    Line2D([0], [0], color="darkgreen", lw=1.5, label="Carreteras"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=10)
plt.title("Simulación de Guerra Civil: Vista Satelital del Palacio de Puebla", fontsize=16, weight="bold")
plt.xlabel("Longitud", fontsize=12)
plt.ylabel("Latitud", fontsize=12)
plt.grid(True, linestyle="--", alpha=0.3)
plt.tight_layout()

# Guardar la "foto" en alta resolución
plt.savefig("foto_palacio_puebla_2025.png", dpi=600, bbox_inches="tight")
print("Foto guardada como 'foto_palacio_puebla_2025.png'")
plt.show()