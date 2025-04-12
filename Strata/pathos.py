import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt

# Crear grafo
G = nx.Graph()

# Añadir nodos con coordenadas aproximadas
G.add_node("Guadalajara", pos=(20.67, -103.33))
G.add_node("Querétaro", pos=(20.59, -100.39))
G.add_node("Ciudad de México", pos=(19.43, -99.13))
G.add_node("Puebla", pos=(19.04, -98.21))
G.add_node("Chihuahua", pos=(28.63, -106.08))
G.add_node("Torreón", pos=(25.54, -103.41))

# Añadir aristas con pesos (distancias aproximadas en km)
G.add_edge("Guadalajara", "Querétaro", weight=350)
G.add_edge("Querétaro", "Ciudad de México", weight=200)
G.add_edge("Ciudad de México", "Puebla", weight=130)
G.add_edge("Chihuahua", "Torreón", weight=450)
G.add_edge("Torreón", "Ciudad de México", weight=800)

# Encontrar rutas más cortas
ruta_jalisco = nx.shortest_path(G, "Guadalajara", "Puebla", weight="weight")
ruta_chihuahua = nx.shortest_path(G, "Chihuahua", "Puebla", weight="weight")
print("Ruta desde Jalisco:", ruta_jalisco)
print("Ruta desde Chihuahua:", ruta_chihuahua)

# Cargar mapa de México (necesitas un shapefile, ej. de INEGI)
mexico_map = gpd.read_file("mex_admbnda_govmex_20210618_SHP/mex_admbndl_admALL_govmex_itos_20210618.shp")

# Graficar
fig, ax = plt.subplots(figsize=(12, 12))
mexico_map.plot(ax=ax, color="lightgrey", edgecolor="black")

# Añadir nodos al mapa
pos = nx.get_node_attributes(G, "pos")
for node, (lat, lon) in pos.items():
    ax.plot(lon, lat, marker="o", color="red", markersize=10)
    ax.text(lon, lat, node, fontsize=8, ha="right")

plt.title("Puntos Estratégicos y Rutas en México")
plt.show()