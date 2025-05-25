from fastapi import FastAPI, HTTPException
from typing import List
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import io
import base64
from pyomo.environ import ConcreteModel, Set, Var, Binary, Objective, Constraint, SolverFactory, value, minimize

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# Cargar y proyectar el grafo de Bogotá
G = ox.graph_from_place("Bogotá, Colombia", network_type="drive")
G = ox.project_graph(G)

@app.post("/ruta-optima")
async def calcular_ruta(coordenadas: List[str]):
    try:
        # Convertir strings "lat,lon" a tuplas
        puntos = []
        for s in coordenadas:
            partes = s.split(",")
            if len(partes) != 2:
                raise ValueError(f"Formato incorrecto: {s}")
            lat = float(partes[0].strip())
            lon = float(partes[1].strip())
            puntos.append((lat, lon))

        # Buscar nodos más cercanos
        nodos = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in puntos]

        # Crear una ruta inicial con todos los puntos para extraer los arcos posibles
        ruta_base = []
        for i in range(len(nodos) - 1):
            tramo = nx.shortest_path(G, nodos[i], nodos[i + 1], weight="length")
            ruta_base += tramo[:-1]
        ruta_base.append(nodos[-1])

        # Arcos y distancias desde la ruta base
        arcos = []
        distancias = {}
        for u, v in zip(ruta_base[:-1], ruta_base[1:]):
            d = G[u][v][0]["length"] / 1000
            arcos.append((u, v))
            distancias[(u, v)] = d
        nodos_unicos = set(n for a in arcos for n in a)

        # Construir modelo Pyomo
        model = ConcreteModel()
        model.A = Set(initialize=arcos, dimen=2)
        model.N = Set(initialize=nodos_unicos)
        model.x = Var(model.A, domain=Binary)
        model.obj = Objective(expr=sum(distancias[i] * model.x[i] for i in model.A), sense=minimize)

        def flujo_balance(model, n):
            if n == nodos[0]:  # origen
                return sum(model.x[i] for i in model.A if i[0] == n) == 1
            elif n == nodos[-1]:  # destino
                return sum(model.x[i] for i in model.A if i[1] == n) == 1
            else:
                return (sum(model.x[i] for i in model.A if i[0] == n) -
                        sum(model.x[i] for i in model.A if i[1] == n)) == 0

        model.flujo = Constraint(model.N, rule=flujo_balance)

        # Resolver
        solver = SolverFactory("cbc")
        result = solver.solve(model, tee=False)

        # Obtener ruta óptima
        ruta_optima = [i for i in model.A if value(model.x[i]) == 1]
        if not ruta_optima:
            raise ValueError("No se pudo calcular la ruta óptima.")

        nodos_ruta = [ruta_optima[0][0]] + [a[1] for a in ruta_optima]

        # Obtener coordenadas
        coordenadas_ruta = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in nodos_ruta]
        google_maps_url = "https://www.google.com/maps/dir/" + "/".join([f"{lat},{lon}" for lat, lon in coordenadas_ruta])

        # Graficar
        fig, ax = ox.plot_graph_route(G, nodos_ruta, route_color="green", node_size=0, show=False, close=False)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)

        # Calcular distancia total
        distancia_total_km = sum(distancias[i] for i in ruta_optima)

        return {
            "mensaje": "Ruta óptima generada",
            "imagen_base64": img_base64,
            "coordenadas": coordenadas_ruta,
            "google_maps_url": google_maps_url,
            "distancia_total_km": round(distancia_total_km, 2)
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))