from fastapi import FastAPI, HTTPException
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import io
import base64

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# Cargar y proyectar grafo de Bogotá
G = ox.graph_from_place("Bogotá, Colombia", network_type="drive")
G = ox.project_graph(G)

@app.post("/ruta-optima")
async def calcular_ruta(coordenadas: list[str]):
    try:
        # Parsear coordenadas "lat,lon" → [(lat, lon), ...]
        puntos = []
        for s in coordenadas:
            partes = s.split(",")
            if len(partes) != 2:
                raise ValueError(f"Formato inválido: {s}")
            lat = float(partes[0].strip())
            lon = float(partes[1].strip())
            puntos.append((lat, lon))

        # Buscar nodos más cercanos en el grafo
        nodos = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in puntos]

        # Construir ruta completa
        ruta_total = []
        distancia_total = 0.0
        for i in range(len(nodos) - 1):
            tramo = nx.shortest_path(G, nodos[i], nodos[i + 1], weight='length')
            ruta_total += tramo[:-1]
            distancia_total += sum(
                G[u][v][0]["length"] for u, v in zip(tramo[:-1], tramo[1:])
            )
        ruta_total.append(nodos[-1])

        # Obtener coordenadas para Google Maps
        coordenadas_ruta = [
            f"{G.nodes[n]['y']},{G.nodes[n]['x']}" for n in ruta_total
        ]
        google_maps_url = (
            "https://www.google.com/maps/dir/" + "/".join(coordenadas_ruta)
        )

        # Dibujar imagen del grafo con la ruta
        fig, ax = ox.plot_graph_route(
            G, ruta_total, route_color="orange", node_size=0, show=False, close=False
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)

        return {
            "imagen_base64": img_base64,
            "nodos_recorridos": coordenadas_ruta,
            "distancia_total_km": round(distancia_total / 1000, 2),
            "google_maps_url": google_maps_url
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))