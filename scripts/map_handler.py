import osmnx as ox
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from scipy.spatial import Delaunay
import random
import geopandas as gpd
from shapely.geometry import Point, LineString



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



def generate_smart_bins(G, num_bins=150):
    """
    Generates fictional waste bins along the edges of the given graph.
    Returns a GeoDataFrame of the bins.
    """
    # 1. Convert the graph edges into a GeoDataFrame to access their geometries
    nodes, edges = ox.graph_to_gdfs(G)
    
    bins_data = []
    
    # 2. Iterate to create bins
    for i in range(num_bins):
        # Pick a random street (edge) to place the bin on
        # edges.index is a tuple of (u, v, key)
        random_edge_idx = random.choice(edges.index)
        
        # Get the geometric shape (LineString) of that street
        edge_geom = edges.loc[random_edge_idx, 'geometry']
        
        # 3. Place the bin somewhere along that street
        # normalized=True means 0.0 is the start of the street, 1.0 is the end
        position_along_street = random.uniform(0.05, 0.95) 
        bin_point = edge_geom.interpolate(position_along_street, normalized=True)
        
        # 4. Generate Simulation Data
        fullness = np.random.randint(0, 100) # 0% to 100% full
        sensor_status = "active" if random.random() > 0.05 else "offline" # 5% chance of broken sensor
        
        # 5. Store the data, explicitly linking it to the street network
        bins_data.append({
            'bin_id': f"BIN-{str(i).zfill(4)}",
            'geometry': bin_point,
            'edge_u': random_edge_idx[0],  # The start node of the street
            'edge_v': random_edge_idx[1],  # The end node of the street
            'fullness_pct': fullness,
            'sensor_status': sensor_status,
            'capacity_liters': random.choice([120, 240, 1100])
        })
        
    # Convert the list of dictionaries into a GeoDataFrame
    bins_gdf = gpd.GeoDataFrame(bins_data, crs=G.graph['crs'])
    return bins_gdf

def plot_city_with_bins(G, bins_gdf):
    """
    Plots the street network and overlays the waste bins, 
    color-coded by how full they are.
    """
    # 1. Plot the base street network (capture the figure and axis)
    fig, ax = ox.plot_graph(
        G, 
        show=False, 
        close=False, 
        node_size=0,         # Hide the intersection nodes for a cleaner look
        edge_color="#333333", 
        edge_linewidth=0.5,
        bgcolor="white"
    )
    
    # 2. Filter bins by fullness for color coding
    critical_bins = bins_gdf[bins_gdf['fullness_pct'] >= 80]
    medium_bins = bins_gdf[(bins_gdf['fullness_pct'] >= 40) & (bins_gdf['fullness_pct'] < 80)]
    empty_bins = bins_gdf[bins_gdf['fullness_pct'] < 40]
    
    # 3. Plot the bins on top of the same axis (`ax=ax`)
    empty_bins.plot(ax=ax, color='green', markersize=10, alpha=0.6, label='< 40% Full')
    medium_bins.plot(ax=ax, color='orange', markersize=15, alpha=0.8, label='40-80% Full')
    critical_bins.plot(ax=ax, color='red', markersize=25, alpha=1.0, label='> 80% Full (Needs Pickup)')
    
    # 4. Add a legend and show
    plt.title("Smart City Waste Management: Real-Time Bin Status", fontsize=14)
    plt.legend(loc="upper left")
    plt.show()


if __name__=="__main__":
    city_name = "Cluj-Napoca"
    network_type = "drive_service"

    G = generate_graph_from_osm(city_name=city_name, network_type=network_type, is_projected=False, should_plot=False)
    # G = generate_fictive_city(should_plot=True, num_edges=800)
    bins_gdf = generate_smart_bins(G)
    plot_city_with_bins(G, bins_gdf)
