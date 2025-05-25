from fastapi import FastAPI, Request, HTTPException
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import uuid
import io
import base64

# FastAPI sin docs
app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# Cargar el grafo de Bogotá
G = ox.graph_from_place("Bogotá, Colombia", network_type='drive')

@app.post("/ruta")
async def calcular_ruta(coordenadas: list[str]):
    try:
        # Convertir strings "lat,lon" a tuplas (lat, lon)
        puntos = []
        for s in coordenadas:
            partes = s.split(",")
            if len(partes) != 2:
                raise ValueError(f"Formato incorrecto: {s}")
            lat = float(partes[0].strip())
            lon = float(partes[1].strip())
            puntos.append((lat, lon))

        # Encontrar nodos más cercanos en el grafo
        nodos = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in puntos]

        # Calcular ruta combinada
        ruta_total = []
        for i in range(len(nodos) - 1):
            tramo = nx.shortest_path(G, nodos[i], nodos[i + 1], weight='length')
            ruta_total += tramo[:-1]
        ruta_total.append(nodos[-1])

        # Graficar la ruta
        fig, ax = ox.plot_graph_route(G, ruta_total, route_color='orange', node_size=0, show=False, close=False)
        buf = io.BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return {"imagen_base64": img_base64}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
