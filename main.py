import os
import math
import time
import concurrent.futures
from flask import Flask, request, jsonify
import networkx as nx
import osmnx as ox
import polyline
from shapely.geometry import LineString  # for type hints if needed
from flask_cors import CORS
app = Flask(__name__)
CORS(app)
GRAPH_FILE = "philippines.graphml"

def load_graph():
    """
    Loads the Philippines road network graph from a local GraphML file.
    If the file doesn't exist, downloads the graph from Overpass,
    saves it locally, and returns the graph.
    """
    if os.path.exists(GRAPH_FILE):
        print(f"Loading existing {GRAPH_FILE} ...")
        G = ox.load_graphml(GRAPH_FILE)
    else:
        print("Downloading from Overpass (this may take a long time)...")
        G = ox.graph_from_place("Philippines", network_type="drive", simplify=True)
        print("Download complete. Saving to graphml ...")
        ox.save_graphml(G, GRAPH_FILE)
        print(f"Saved to {GRAPH_FILE}.")
    return G

# Pre-load the graph when the API starts.
G = load_graph()

###############################################################################
#                              A* with k-Step Lookahead                       #
###############################################################################

class KaryHeap:
    def __init__(self, k):
        if k < 2:
            raise ValueError("k must be at least 2")
        self.k = k
        self.data = []

    def push(self, item):
        self.data.append(item)
        self._sift_up(len(self.data) - 1)

    def pop(self):
        if not self.data:
            raise IndexError("pop from an empty heap")
        return_item = self.data[0]
        last_item = self.data.pop()
        if self.data:
            self.data[0] = last_item
            self._sift_down(0)
        return return_item

    def _sift_up(self, idx):
        item = self.data[idx]
        while idx > 0:
            parent = (idx - 1) // self.k
            if item >= self.data[parent]:
                break
            self.data[idx] = self.data[parent]
            idx = parent
        self.data[idx] = item

    def _sift_down(self, idx):
        n = len(self.data)
        item = self.data[idx]
        while True:
            min_child_idx = None
            min_child_item = None
            for i in range(1, self.k + 1):
                child_idx = self.k * idx + i
                if child_idx >= n:
                    break
                if min_child_item is None or self.data[child_idx] < min_child_item:
                    min_child_item = self.data[child_idx]
                    min_child_idx = child_idx
            if min_child_idx is None or item <= min_child_item:
                break
            self.data[idx] = min_child_item
            idx = min_child_idx
        self.data[idx] = item

    def is_empty(self):
        return not self.data

def heuristic(G, u, v, h_cache):
    # Euclidean distance between nodes u and v (using node 'x' and 'y' attributes)
    if (u, v) not in h_cache:
        h_cache[(u, v)] = math.sqrt(
            (G.nodes[v]['x'] - G.nodes[u]['x']) ** 2 +
            (G.nodes[v]['y'] - G.nodes[u]['y']) ** 2
        )
    return h_cache[(u, v)]

def reconstruct_path(came_from, start, goal):
    path = []
    current = goal
    while current != start:
        path.append(current)
        current = came_from[current]
    path.append(start)
    path.reverse()
    return path

def astar_path_k_lookahead(G, start, goal, k, heap_k=4):
    """
    Runs A* with k-step lookahead. For k <= 7, lookahead is sequential;
    for k > 7, uses parallel lookahead with ThreadPoolExecutor.
    """
    print(f"Starting A* with k-step lookahead: k={k}, heap_k={heap_k}")
    open_list = KaryHeap(heap_k)
    open_list.push((0, start))
    closed_set = set()
    came_from = {}
    cost_so_far = {start: 0}
    heuristic_cache = {}

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=16)

    def k_step_lookahead(node, k_remaining, visited, cumulative_cost, executor, h_cache):
        if k_remaining == 0 or node == goal:
            return cumulative_cost + heuristic(G, node, goal, h_cache), node
        visited.add(node)
        min_cost = float('inf')
        best_end_node = node
        for neighbor in G.neighbors(node):
            if neighbor in visited:
                continue
            edge_data = G.get_edge_data(node, neighbor)
            edge_cost = edge_data.get('length', 1) if edge_data else 1
            path_cost, end_node = k_step_lookahead(neighbor, k_remaining - 1,
                                                   visited.copy(),
                                                   cumulative_cost + edge_cost,
                                                   executor, h_cache)
            if path_cost < min_cost:
                min_cost = path_cost
                best_end_node = end_node
            if end_node == goal:
                return path_cost, end_node
        return min_cost, best_end_node

    while not open_list.is_empty():
        current_cost, current = open_list.pop()
        if current in closed_set:
            continue

        closed_set.add(current)

        if current == goal:
            executor.shutdown()
            return reconstruct_path(came_from, start, goal), None, None

        futures = {}
        for neighbor in G.neighbors(current):
            if neighbor in closed_set:
                continue
            edge_data = G.get_edge_data(current, neighbor)
            edge_cost = edge_data.get('length', 1) if edge_data else 1
            new_cost = cost_so_far[current] + edge_cost
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                # Use parallel lookahead if k > 7, otherwise sequential.
                if k > 7:
                    futures[neighbor] = executor.submit(
                        k_step_lookahead, neighbor, k, {current}, 0,
                        executor, heuristic_cache
                    )
                else:
                    lookahead_cost, _ = k_step_lookahead(
                        neighbor, k, {current}, 0,
                        executor, heuristic_cache
                    )
                    total_estimated_cost = new_cost + lookahead_cost
                    came_from[neighbor] = current
                    open_list.push((total_estimated_cost, neighbor))

        if k > 7:
            for neighbor, future in futures.items():
                try:
                    lookahead_cost, _ = future.result()
                    total_estimated_cost = cost_so_far[neighbor] + lookahead_cost
                    came_from[neighbor] = current
                    open_list.push((total_estimated_cost, neighbor))
                except Exception as e:
                    print(f"Error processing neighbor {neighbor}: {e}")
                    continue

    executor.shutdown()
    print("No path found.")
    return None, None, None

###############################################################################
#                        compute_polyline with geometry                       #
###############################################################################

def compute_polyline(start_coords, end_coords, k_value=5):
    """
    Given start and end coordinates as [lat, lon],
    runs A* with k-step lookahead using the provided k_value (and a 4-ary heap),
    then extracts each edge's geometry to produce a road-accurate polyline.
    """
    try:
        start_node = ox.distance.nearest_nodes(G, X=start_coords[1], Y=start_coords[0])
        end_node = ox.distance.nearest_nodes(G, X=end_coords[1], Y=end_coords[0])
    except Exception as e:
        return None, f"Error finding nearest nodes: {str(e)}"

    # Use A* with k-step lookahead with the provided k_value.
    route, _, _ = astar_path_k_lookahead(G, start_node, end_node, k=k_value, heap_k=4)
    if route is None:
        return None, "No path found."

    # Build a list of (lat, lon) points that follows each edge's actual geometry.
    route_coords = []
    for u, v in zip(route[:-1], route[1:]):
        edge_data = G.get_edge_data(u, v)
        if not edge_data:
            route_coords.append((G.nodes[u]["y"], G.nodes[u]["x"]))
            continue
        found_geometry = False
        for key, data in edge_data.items():
            if "geometry" in data:
                geom = data["geometry"]  # Shapely LineString
                xs, ys = geom.xy
                for i in range(len(xs)):
                    route_coords.append((ys[i], xs[i]))
                found_geometry = True
                break
        if not found_geometry:
            route_coords.append((G.nodes[u]["y"], G.nodes[u]["x"]))
    last_node = route[-1]
    route_coords.append((G.nodes[last_node]["y"], G.nodes[last_node]["x"]))
    try:
        encoded_polyline = polyline.encode(route_coords)
    except Exception as e:
        return None, f"Error encoding polyline: {str(e)}"

    return encoded_polyline, None

###############################################################################
#                               Flask API Endpoint                            #
###############################################################################

@app.route("/snap", methods=["GET"])
def snap_endpoint():
    """
    Expects query parameters: lat, lon.
    Returns JSON: {"snapped_lat": <float>, "snapped_lon": <float>}
    """
    lat_str = request.args.get("lat")
    lon_str = request.args.get("lon")
    if not lat_str or not lon_str:
        return jsonify({"error": "Missing lat or lon"}), 400

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return jsonify({"error": "Invalid lat/lon format"}), 400

    try:
        snapped_node = ox.distance.nearest_nodes(G, X=lon, Y=lat)
        snapped_lat = G.nodes[snapped_node]["y"]
        snapped_lon = G.nodes[snapped_node]["x"]
    except Exception as e:
        return jsonify({"error": f"Snap failed: {str(e)}"}), 500

    return jsonify({
        "snapped_lat": snapped_lat,
        "snapped_lon": snapped_lon
    })

@app.route("/route", methods=["GET", "POST"])
def route_endpoint():
    """
    API endpoint that accepts start and end coordinates and returns an encoded polyline.
    
    GET request:
      /route?start=lat,lon&end=lat,lon&k=value
    POST request (JSON):
      {"start": "lat,lon", "end": "lat,lon", "k": value}
    """
    if request.method == "POST":
        data = request.get_json()
        start = data.get("start")
        end = data.get("end")
        k_value = data.get("k", 5)  # Default k=5 if not provided
    else:
        start = request.args.get("start")
        end = request.args.get("end")
        k_value = request.args.get("k", 5)  # Default k=5 if not provided
        try:
            k_value = int(k_value)
        except:
            k_value = 5

    if not start or not end:
        return jsonify({"error": "Missing start or end coordinates"}), 400

    try:
        start_coords = list(map(float, start.split(","))) if isinstance(start, str) else start
        end_coords = list(map(float, end.split(","))) if isinstance(end, str) else end
        if len(start_coords) != 2 or len(end_coords) != 2:
            raise ValueError("Coordinates must have two values: lat,lon")
    except Exception as e:
        return jsonify({"error": f"Invalid coordinates format: {str(e)}"}), 400

    encoded_poly, error = compute_polyline(start_coords, end_coords, k_value=k_value)
    if error:
        return jsonify({"error": error}), 500

    return jsonify({"polyline": encoded_poly})

if __name__ == "__main__":
    # Run the Flask API on the default port 5000. Set debug=False in production.
    app.run(debug=False, port=8080)
