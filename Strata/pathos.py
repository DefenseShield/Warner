import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import requests
import zipfile
import os
import shutil
import tempfile

# Crear directorio temporal para el shapefile
temp_dir = tempfile.mkdtemp()

# Descargar shapefile de Geofabrik
url = "http://download.geofabrik.de/north-america/mexico-latest-free.shp.zip"
zip_path = os.path.join(temp_dir, "mexico_shp.zip")

print("Descargando shapefile desde Geofabrik...")
response = requests.get(url, stream=True)
if response.status_code == 200:
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
else:
    print("Error al descargar el shapefile. Código de estado:", response.status_code)
    exit()

# Descomprimir el archivo
print("Descomprimiendo shapefile...")
with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

# Buscar la capa de carreteras
roads_shp = None
for root, _, files in os.walk(temp_dir):
    for file in files:
        if file == "gis_osm_roads_free_1.shp":
            roads_shp = os.path.join(root, file)
            break
if not roads_shp:
    print("No se encontró gis_osm_roads_free_1.shp en el archivo descargado.")
    shutil.rmtree(temp_dir)
    exit()

# Crear grafo para la simulación
G = nx.Graph()

# Añadir nodos con coordenadas (latitud, longitud)
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

# Añadir aristas con pesos (distancias en km, ajustadas por terreno)
edges = [
    ("Chihuahua", "Torreón", 450),      # Desierto
    ("Torreón", "Ciudad de México", 800),  # Terreno mixto
    ("Ciudad de México", "Puebla", 130),   # Montañoso
    ("Guadalajara", "Querétaro", 350),     # Jalisco
    ("Querétaro", "Ciudad de México", 200),# Jalisco
]

for start, end, weight in edges:
    G.add_edge(start, end, weight=weight)

# Calcular rutas más cortas
ruta_chihuahua = nx.shortest_path(G, "Chihuahua", "Puebla", weight="weight")
ruta_jalisco = nx.shortest_path(G, "Guadalajara", "Puebla", weight="weight")
print("Ruta desde Chihuahua:", ruta_chihuahua)
print("Ruta desde Jalisco:", ruta_jalisco)

# Cargar shapefile de carreteras
try:
    roads = gpd.read_file(roads_shp)
    # Filtrar carreteras relevantes (autopistas, primarias, secundarias)
    roads = roads[roads["fclass"].isin(["motorway", "trunk", "primary", "secondary"])]
except Exception as e:
    print(f"Error al cargar el shapefile: {e}")
    shutil.rmtree(temp_dir)
    exit()

# Graficar
fig, ax = plt.subplots(figsize=(15, 12))

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
plt.title("Simulación de Guerra Civil: Rutas Estratégicas a Puebla", fontsize=16, weight="bold")
plt.xlabel("Longitud", fontsize=12)
plt.ylabel("Latitud", fontsize=12)
plt.grid(True, linestyle="--", alpha=0.3)
plt.tight_layout()

# Guardar el mapa
plt.savefig("mapa_estrategico_mexico.png", dpi=300, bbox_inches="tight")
plt.show()

# Limpiar directorio temporal
shutil.rmtree(temp_dir)
print("Directorio temporal limpiado.")