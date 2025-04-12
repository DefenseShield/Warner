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

# Asegurar backend interactivo
plt.switch_backend('Qt5Agg')  # O 'TkAgg' si Qt5 no está disponible

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

# Definir el área inicial alrededor del Palacio Municipal de Puebla
palacio_coords = (19.0433, -98.1981)  # Latitud, Longitud
delta = 0.009  # Aproximadamente 1 km en grados (1 grado ~ 111 km)
bbox_coords = [
    palacio_coords[1] - delta,  # Longitud mínima
    palacio_coords[0] - delta,  # Latitud mínima
    palacio_coords[1] + delta,  # Longitud máxima
    palacio_coords[0] + delta   # Latitud máxima
]
bbox = BBox(bbox=bbox_coords, crs=CRS.WGS84)

# Filtrar carreteras dentro del bounding box inicial
roads = roads.cx[bbox_coords[0]:bbox_coords[2], bbox_coords[1]:bbox_coords[3]]

# Descargar imagen satelital inicial con Sentinel Hub
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

print("Descargando imagen satelital inicial desde Sentinel Hub...")
try:
    image = request.get_data(save_data=True)[0]
except Exception as e:
    print(f"Error al descargar la imagen satelital inicial: {e}")
    print("Verifica tu conexión o las credenciales en .env.")
    exit()

# Graficar mapa interactivo
fig, ax = plt.subplots(figsize=(15, 12))

# Mostrar imagen satelital
extent = [bbox_coords[0], bbox_coords[2], bbox_coords[1], bbox_coords[3]]
im = ax.imshow(image, extent=extent, alpha=0.9)

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
plt.title("Simulación de Guerra Civil: Vista Satelital del Palacio de Puebla (Interactiva)", fontsize=16, weight="bold")
plt.xlabel("Longitud", fontsize=12)
plt.ylabel("Latitud", fontsize=12)
plt.grid(True, linestyle="--", alpha=0.3)

# Función para manejar Ctrl + Clic
def on_click(event):
    if event.button == 1 and event.key == 'control':  # Clic izquierdo + Ctrl
        # Obtener coordenadas del clic
        lon, lat = event.xdata, event.ydata
        if lon is None or lat is None:
            print("Clic fuera del área del mapa.")
            return

        # Obtener el nivel de zoom actual
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        zoom_width = xlim[1] - xlim[0]  # Ancho en grados
        zoom_height = ylim[1] - ylim[0]  # Alto en grados

        # Definir nuevo bounding box centrado en el clic
        delta = max(zoom_width, zoom_height) / 2  # Usar el mayor para mantener proporción
        new_bbox_coords = [
            lon - delta,
            lat - delta,
            lon + delta,
            lat + delta
        ]
        new_bbox = BBox(bbox=new_bbox_coords, crs=CRS.WGS84)

        # Descargar nueva imagen satelital
        new_request = SentinelHubRequest(
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
            bbox=new_bbox,
            size=[2048, 2048],  # Alta resolución
            config=config,
        )

        print(f"Descargando nueva imagen satelital centrada en ({lat}, {lon})...")
        try:
            new_image = new_request.get_data(save_data=True)[0]
        except Exception as e:
            print(f"Error al descargar la nueva imagen satelital: {e}")
            return

        # Crear nueva figura para la "foto"
        fig_new, ax_new = plt.subplots(figsize=(15, 12))
        new_extent = [new_bbox_coords[0], new_bbox_coords[2], new_bbox_coords[1], new_bbox_coords[3]]
        ax_new.imshow(new_image, extent=new_extent, alpha=0.9)

        # Filtrar carreteras para el nuevo área
        new_roads = roads.cx[new_bbox_coords[0]:new_bbox_coords[2], new_bbox_coords[1]:new_bbox_coords[3]]
        new_roads.plot(ax=ax_new, color="darkgreen", linewidth=1.5, alpha=0.7)

        # Añadir marcador en el punto del clic
        ax_new.plot(lon, lat, marker="x", color="red", markersize=15, markeredgewidth=2)
        ax_new.text(lon + 0.001, lat, "Punto Seleccionado", fontsize=12, ha="left", weight="bold", color="red")

        # Personalizar nueva figura
        legend_elements_new = [
            Line2D([0], [0], marker="x", color="w", markerfacecolor="red", markeredgecolor="red", markersize=15, label="Punto Seleccionado"),
            Line2D([0], [0], color="darkgreen", lw=1.5, label="Carreteras"),
        ]
        ax_new.legend(handles=legend_elements_new, loc="upper left", fontsize=10)
        plt.title(f"Vista Satelital Centrada en ({lat:.4f}, {lon:.4f})", fontsize=16, weight="bold")
        plt.xlabel("Longitud", fontsize=12)
        plt.ylabel("Latitud", fontsize=12)
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.tight_layout()

        # Guardar la "foto"
        filename = f"foto_satelital_{lat:.4f}_{lon:.4f}_2025.png"
        plt.savefig(filename, dpi=600, bbox_inches="tight")
        print(f"Foto guardada como '{filename}'")
        plt.close(fig_new)

# Conectar el evento de clic
fig.canvas.mpl_connect('button_press_event', on_click)

# Mostrar mapa interactivo
plt.tight_layout()
plt.show()