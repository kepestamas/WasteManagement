import osmnx as ox
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from scipy.spatial import Delaunay
import random



def generate_graph_from_osm(city_name, network_type, is_projected=False, should_plot=False):
    """
    Generates an nx graph from real city infratructure using OSMnx.

    Parameters:
    - city_name: the name of the city and specifiers such as county, state or country
    - network_tye: \"drive\" or \"drive_service\" are used for car networks
    - is_projected: False by default, if True, the returned graph uses meters instead of lon/lat
    - should_plot: False by default, if True, a graph plot will be createdin the plots folder  
    """
    graph = ox.graph_from_place(city_name, network_type=network_type)
    graph_projected = ox.project_graph(graph)
    if is_projected:
        result_graph = graph_projected.copy()
    else:
        result_graph = graph.copy()
    if should_plot:
        ox.plot_graph(graph_projected, node_size=1, edge_linewidth=0.4, filepath="../plots/"+city_name+"_"+network_type+".png", dpi=1000, save=True, show=False)
    return result_graph


def generate_fictive_city(num_nodes=500, num_edges=700, center_lat=40.7, center_lon=-74.0, should_plot=False, city_name="Fictional City"):
    """
    Generates a fictional city street network compatible with OSMnx.
    
    Parameters:
    - num_nodes: The number of intersections.
    - num_edges: The target number of street connections (must be <= 3*num_nodes - 6).
    - center_lat, center_lon: The geographic center of the fictional city.
    - city_name: the name of the fictional city
    - should_plot: False by default, if True, a graph plot will be createdin the plots folder  
    """
    
    # 1. Initialize an OSMnx-compatible MultiDiGraph
    G = nx.MultiDiGraph()
    G.graph['crs'] = 'epsg:4326'  # Standard WGS84 coordinate reference system
    G.graph['name'] = city_name
    
    # 2. Generate Nodes (Intersections)
    # Using a normal distribution creates a dense "downtown" and sparse "suburbs"
    x_coords = np.random.normal(loc=center_lon, scale=0.03, size=num_nodes)
    y_coords = np.random.normal(loc=center_lat, scale=0.03, size=num_nodes)
    
    for i in range(num_nodes):
        # OSMnx requires 'x', 'y', and 'osmid' for nodes
        G.add_node(i, x=x_coords[i], y=y_coords[i], osmid=i)
        
    # 3. Generate Realistic Planar Edges (Streets) via Delaunay Triangulation
    points = np.column_stack((x_coords, y_coords))
    tri = Delaunay(points)
    
    # Extract unique edges from the triangles
    raw_edges = set()
    for simplex in tri.simplices:
        raw_edges.add(tuple(sorted((simplex[0], simplex[1]))))
        raw_edges.add(tuple(sorted((simplex[1], simplex[2]))))
        raw_edges.add(tuple(sorted((simplex[2], simplex[0]))))
        
    raw_edges = list(raw_edges)
    
    # 4. Parameterize Connections (Pruning)
    # Delaunay creates the maximum planar edges. We shuffle and slice to hit your target.
    max_possible_edges = len(raw_edges)
    if num_edges > max_possible_edges:
        print(f"Warning: For {num_nodes} nodes, max planar edges is ~{max_possible_edges}. Capping to this.")
        num_edges = max_possible_edges
        
    random.shuffle(raw_edges)
    selected_edges = raw_edges[:num_edges]
    
    # 5. Populate OSMnx Edge Attributes
    street_types = ['residential', 'tertiary', 'secondary', 'primary']
    street_probs = [0.70, 0.15, 0.10, 0.05] # Mostly residential
    
    for u, v in selected_edges:
        # Calculate rough distance in meters (1 degree ~ 111,000 meters)
        # For a completely accurate measure, use ox.distance.great_circle_vec
        dx = (x_coords[u] - x_coords[v]) * 111000 * np.cos(np.radians(center_lat))
        dy = (y_coords[u] - y_coords[v]) * 111000
        length = np.sqrt(dx**2 + dy**2)
        
        hw_type = np.random.choice(street_types, p=street_probs)
        is_oneway = random.random() < 0.15 # 15% chance of being a one-way street
        street_name = f"Route {u}-{v}"
        
        # Add forward edge
        G.add_edge(u, v, key=0, 
                osmid=f"edge_{u}_{v}",
                length=length, 
                highway=hw_type, 
                oneway=is_oneway, 
                name=street_name)
        
        # Add reverse edge if it's a two-way street
        if not is_oneway:
            G.add_edge(v, u, key=0, 
                    osmid=f"edge_{v}_{u}",
                    length=length, 
                    highway=hw_type, 
                    oneway=False, 
                    name=street_name)
            
    #TODO: consider removing isolated nodes
    #TODO: consider differences between projected and coordinate variants
            
    if should_plot:
        ox.plot_graph(G, node_size=1, edge_linewidth=0.4, filepath="../plots/"+G.graph["name"]+"_fictional.png", dpi=1000, save=True, show=False)
    return G


if __name__=="__main__":
    city_name = "Budapest"
    network_type = "drive_service"

    generate_graph_from_osm(city_name=city_name, network_type=network_type, is_projected=True, should_plot=True)
    # generate_fictive_city(should_plot=True, num_edges=800)
