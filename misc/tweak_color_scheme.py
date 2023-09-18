# %ngql USE basketballplayer;
# %ngql MATCH ()-[e]->() RETURN e LIMIT 6;

result_df = _

from nebula3.data.DataObject import Node, Relationship, PathWrapper
from pyvis.network import Network
from IPython.display import display, IFrame, HTML

COLORS = ["#e2dbbe", "#d5d6aa", "#9dbbae", "#769fb6", "#188fa7"]


def get_color(input_str):
    hash_val = 0
    for char in input_str:
        hash_val = (hash_val * 31 + ord(char)) & 0xFFFFFFFF
    return COLORS[hash_val % len(COLORS)]


def render_pd_item(g, item):
    if isinstance(item, Node):
        node_id = item.get_id().cast()
        tags = item.tags()  # list of strings
        props = dict()
        for tag in tags:
            props.update(item.properties(tag))

        g.add_node(node_id, label=node_id, title=str(props), color=get_color(node_id))
    elif isinstance(item, Relationship):
        src_id = item.start_vertex_id().cast()
        dst_id = item.end_vertex_id().cast()
        edge_name = item.edge_name()
        props = item.properties()
        # ensure start and end vertex exist in graph
        if not src_id in g.node_ids:
            g.add_node(
                src_id,
                label=str(src_id),
                title=str(src_id),
                color=get_color(src_id),
            )
        if not dst_id in g.node_ids:
            g.add_node(
                dst_id,
                label=str(dst_id),
                title=str(dst_id),
                color=get_color(dst_id),
            )
        label = f"{props}\n{edge_name}" if props else edge_name
        g.add_edge(src_id, dst_id, label=label, title=str(props))
    elif isinstance(item, PathWrapper):
        for node in item.nodes():
            render_pd_item(g, node)
        for edge in item.relationships():
            render_pd_item(g, edge)
    elif isinstance(item, list):
        for it in item:
            render_pd_item(g, it)


g = Network(
    notebook=True,
    directed=True,
    cdn_resources="in_line",
    height="500px",
    width="100%",
)
for x, row in result_df.iterrows():
    for item in row:
        render_pd_item(g, item)
g.repulsion(
    node_distance=100,
    central_gravity=0.2,
    spring_length=200,
    spring_strength=0.05,
    damping=0.09,
)

g_html_string = g.generate_html("nebulagraph.html")

with open("nebulagraph.html", "w", encoding='utf-8') as f:
    f.write(g_html_string)

display(IFrame(src="nebulagraph.html", width="100%", height="500px"))
