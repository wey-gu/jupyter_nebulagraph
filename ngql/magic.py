import logging

from IPython.core.magic import (
    Magics,
    magics_class,
    line_cell_magic,
    needs_local_scope,
)
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring

from typing import Dict, List
import networkx as nx


from jinja2 import Template, Environment, meta
from traitlets.config.configurable import Configurable
from traitlets import Bool, Int, Unicode

from nebula3.data.DataObject import Node, Relationship, PathWrapper
from nebula3.gclient.net import ConnectionPool as NebulaConnectionPool
from nebula3.Config import Config as NebulaConfig


rel_query_sample_edge = Template(
    """
MATCH ()-[e:`{{ edge_type }}`]->()
RETURN [src(e), dst(e)] AS sample_edge LIMIT 1
"""
)


rel_query_edge_type = Template(
    """
MATCH (m)-[:`{{ edge_type }}`]->(n)
  WHERE id(m) == "{{ src_id }}" AND id(n) == "{{ dst_id }}"
RETURN tags(m)[0] AS src_tag, tags(n)[0] AS dst_tag
"""
)


CONNECTION_POOL_INIT_FAILURE = -2  # Failure occurred during connection_pool.init
CONNECTION_POOL_NONE = -1  # self.connection_pool was never initiated
CONNECTION_POOL_EXISTED = 0  # self.connection_pool existed & no new created
CONNECTION_POOL_CREATED = 1  # self.connection_pool newly created/recreated

STYLE_PANDAS = "pandas"
STYLE_RAW = "raw"

# COLORS = ["#E2DBBE", "#D5D6AA", "#9DBBAE", "#769FB6", "#188FA7"]
# solarized dark
COLORS = [
    "#93A1A1",
    "#B58900",
    "#CB4B16",
    "#DC322F",
    "#D33682",
    "#6C71C4",
    "#268BD2",
    "#2AA198",
    "#859900",
]

ESCAPE_ARROW_STRING = "__ar_row__"


def truncate(string: str, length: int = 10) -> str:
    if len(string) > length:
        return string[:length] + ".."
    else:
        return string


def get_color(input_str):
    hash_val = 0
    for char in input_str:
        hash_val = (hash_val * 31 + ord(char)) & 0xFFFFFFFF
    return COLORS[hash_val % len(COLORS)]


@magics_class
class IPythonNGQL(Magics, Configurable):
    ngql_verbose = Bool(False, config=True, help="Set verbose mode")
    max_connection_pool_size = Int(
        None,
        config=True,
        allow_none=True,
        help="Maximum Nebula Connection Pool Size",
    )
    ngql_result_style = Unicode(
        STYLE_PANDAS,
        config=True,
        allow_none=True,
        help="Accepted values in ('pandas', 'raw'):"
        " pandas refers to pandas DataFrame,"
        " raw refers to raw thrift data type comes with nebula-python.",
    )

    def __init__(self, shell):
        Magics.__init__(self, shell=shell)

        self.shell.configurables.append(self)
        self.connection_pool = None
        self.space = None
        self.connection_info = None
        self.credential = None

    @needs_local_scope
    @line_cell_magic
    @magic_arguments()
    @argument("line", default="", nargs="*", type=str, help="ngql line")
    @argument("-addr", "--address", type=str, help="IP address")
    @argument("-P", "--port", type=int, help="Port number")
    @argument("-u", "--user", type=str, help="Username")
    @argument("-p", "--password", type=str, help="Password")
    @argument("-f", "--file", type=str, help="Run a NGQL file from a path")  # TBD
    @argument("-c", "--close", type=str, help="Close the connection")  # TBD
    def ngql(self, line, cell=None, local_ns={}):
        """Magic that works both as %ngql and as %%ngql"""
        if line == "help":
            return self._help_info()

        cell = self._render_cell_vars(cell, local_ns)

        # Replace "->" with ESCAPE_ARROW_STRING to avoid argument parsing issues
        modified_line = line.replace("->", ESCAPE_ARROW_STRING)

        args = parse_argstring(self.ngql, modified_line)

        connection_state = self._init_connection_pool(args)
        if self.ngql_verbose:
            print(f"[DEBUG] Connection State: { connection_state }")
        if connection_state < 0:
            print("[ERROR] Connection is not ready")
            return f"Connection State: { connection_state }"
        if connection_state == CONNECTION_POOL_CREATED:
            print("Connection Pool Created")
            if not cell:
                return self._stylized(self._show_spaces())
            else:
                # When connection info in first line and with nGQL lines followed
                return self._stylized(self._execute(cell))
        if connection_state == CONNECTION_POOL_EXISTED:
            # Restore "->" in the query before executing it
            query = (
                line.replace(ESCAPE_ARROW_STRING, "->") + "\n" + (cell if cell else "")
            )
            return self._stylized(self._execute(query))
        else:  # We shouldn't reach here
            return f"Nothing triggerred, Connection State: { connection_state }"

    def _init_connection_pool(self, args):
        connection_info = (args.address, args.port, args.user, args.password)
        if any(connection_info):
            if not all(connection_info):
                raise ValueError(
                    "One or more arguments missing: address, port, user, "
                    "password should None or all be provided."
                )
            else:  # all connection information ready
                connection_pool = NebulaConnectionPool()
                config = NebulaConfig()
                if self.max_connection_pool_size:
                    config.max_connection_pool_size = self.max_connection_pool_size

                self.credential = args.user, args.password
                connect_init_result = connection_pool.init(
                    [(args.address, args.port)], config
                )
                if not connect_init_result:
                    return CONNECTION_POOL_INIT_FAILURE
                else:
                    self.connection_pool = connection_pool
                    return CONNECTION_POOL_CREATED

        # else a.k.a not any(connection_info)
        if self.connection_pool is not None:
            return CONNECTION_POOL_EXISTED
        else:
            return CONNECTION_POOL_NONE

    def _render_cell_vars(self, cell, local_ns):
        if cell is not None:
            env = Environment()
            cell_vars = meta.find_undeclared_variables(env.parse(cell))
            cell_params = {}
            for variable in cell_vars:
                if variable in local_ns:
                    cell_params[variable] = local_ns[variable]
                else:
                    raise NameError(variable)
            cell_template = Template(cell)
            cell = cell_template.render(**cell_params)
            if self.ngql_verbose:
                print(f"Query String:\n { cell }")
        return cell

    def _get_session(self):
        logger = logging.getLogger()
        # FIXME(wey-gu): introduce configurable options here via traitlets
        # Here let's disable the nebula-python logger as we consider
        # most users here are data scientists who would share the
        # notebook, thus connection info shouldn't be revealed unless
        # explicitly specified
        logger.disabled = True
        return self.connection_pool.get_session(*self.credential)

    def _show_spaces(self):
        session = self._get_session()
        try:
            result = session.execute("SHOW SPACES")
            self._auto_use_space(result=result)
        except Exception as e:
            print(f"[ERROR]:\n { e }")
        finally:
            session.release()
        return result

    def _auto_use_space(self, result=None):
        if result is None:
            session = self._get_session()
            result = session.execute("SHOW SPACES;")

        if result.row_size() == 1:
            self.space = result.row_values(0)[0].cast()

    def _execute(self, query):
        session = self._get_session()
        query = query.replace("\\\n", "\n")
        try:
            if self.space is not None:  # Always use space automatically
                session.execute(f"USE { self.space }")
            result = session.execute(query)
            assert result.is_succeeded(), f"Query Failed:\n { result.error_msg() }"
            self._remember_space(result)
        except Exception as e:
            print(f"[ERROR]:\n { e }")
        finally:
            session.release()
        return result

    def _remember_space(self, result):
        last_space_used = result.space_name()
        if last_space_used != "":
            self.space = last_space_used

    def _stylized(self, result):
        if self.ngql_result_style == STYLE_PANDAS:
            try:
                import pandas as pd
            except ImportError:
                raise ImportError("Please install pandas to use STYLE_PANDAS")

            columns = result.keys()
            d: Dict[str, list] = {}
            for col_num in range(result.col_size()):
                col_name = columns[col_num]
                col_list = result.column_values(col_name)
                d[col_name] = [x.cast() for x in col_list]
            return pd.DataFrame(d)
        elif self.ngql_result_style == STYLE_RAW:
            return result
        else:
            raise ValueError("Unknown ngql_result_style")

    @staticmethod
    def _help_info():
        help_info = """

        Supported Configurations:
        ------------------------
        
        > How to config ngql_result_style in "raw", "pandas"
        %config IPythonNGQL.ngql_result_style="raw"
        %config IPythonNGQL.ngql_result_style="pandas"

        > How to config ngql_verbose in True, False
        %config IPythonNGQL.ngql_verbose=True

        > How to config max_connection_pool_size
        %config IPythonNGQL.max_connection_pool_size=10

        Quick Start:
        -----------

        > Connect to Neubla Graph
        %ngql --address 127.0.0.1 --port 9669 --user user --password password

        > Use Space
        %ngql USE basketballplayer

        > Query
        %ngql SHOW TAGS;

        > Multile Queries
        %%ngql
        SHOW TAGS;
        SHOW HOSTS;

        Reload ngql Magic
        %reload_ext ngql

        > Variables in query, we are using Jinja2 here
        name = "nba"
        %ngql USE "{{ name }}"

        > Query and draw the graph

        %ngql GET SUBGRAPH 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;

        %ng_draw

        > Query and draw the graph schema

        %ng_draw_schema

        > Load data from CSV file into NebulaGraph as vertices or edges
        %ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer

        #actor.csv
        "player999","Tom Hanks",30
        "player1000","Tom Cruise",40

        %ng_load --source follow_with_rank.csv --edge follow --src 0 --dst 1 --props 2:degree --rank 3 --space basketballplayer

        #follow_with_rank.csv
        "player999","player1000",50,1

        %ng_load --source follow.csv --edge follow --src 0 --dst 1 --props 2:degree --space basketballplayer

        #follow.csv
        "player999","player1000",50

        %ng_load --source https://github.com/wey-gu/ipython-ngql/raw/main/examples/actor.csv --tag player --vid 0 --props 1:name,2:age --space demo_basketballplayer -b 2


        """
        print(help_info)
        return

    @needs_local_scope
    @line_cell_magic
    @magic_arguments()
    @argument("line", default="", nargs="*", type=str, help="ngql")
    def ng_draw(self, line, cell=None, local_ns={}):
        """
        Draw the graph with the output of the last execution query
        """
        try:
            import pandas as pd
            from pyvis.network import Network
            from IPython.display import display, IFrame, HTML

            # import get_ipython
            from IPython import get_ipython

        except ImportError:
            raise ImportError("Please install pyvis to draw the graph")
        # when `%ngql foo`, varible_name is "foo", else it's "_"
        variable_name = line.strip() or "_"
        # Check if the last execution result is available in the local namespace
        if variable_name not in local_ns:
            return "No result found, please execute a query first."
        result_df = local_ns[variable_name]
        assert isinstance(
            result_df, pd.DataFrame
        ), "Result is not in Pandas DataFrame Style"

        # Create a graph
        g = Network(
            notebook=True,
            directed=True,
            cdn_resources="in_line",
            height="500px",
            width="100%",
            bgcolor="#002B36",
            font_color="#93A1A1",
            neighborhood_highlight=True,
        )
        g_nx = nx.MultiDiGraph()
        for _, row in result_df.iterrows():
            for item in row:
                self.render_pd_item(g, g_nx, item)

        g.repulsion(
            node_distance=90,
            central_gravity=0.2,
            spring_length=200,
            spring_strength=0.05,
            damping=0.09,
        )
        # g.show_buttons(filter_='physics')
        # return g.show("nebulagraph_draw.html", notebook=True)
        g_html_string = g.generate_html("nebulagraph.html")
        with open("nebulagraph.html", "w", encoding="utf-8") as f:
            f.write(g_html_string)
        # detect if we are in colab or not
        try:
            if "google.colab" in str(get_ipython()):
                display(HTML(g_html_string))
            else:
                display(IFrame(src="nebulagraph.html", width="100%", height="500px"))
        except Exception as e:
            print(f"[WARN]: failed to display the graph\n { e }")
            try:
                display(IFrame(src="nebulagraph.html", width="100%", height="500px"))
            except Exception as e:
                print(f"[WARN]: failed to display the graph\n { e }")

        return g

    @line_cell_magic
    @magic_arguments()
    @argument("line", default="", nargs="?", type=str, help="space name")
    def ng_draw_schema(self, line, cell=None, local_ns={}):
        try:
            from pyvis.network import Network
            from IPython.display import display, IFrame, HTML

            # import get_ipython
            from IPython import get_ipython

        except ImportError:
            raise ImportError("Please install pyvis to draw the graph schema")

        args = parse_argstring(self.ng_draw_schema, line)
        space = args.line if args.line else self.space
        if space is None:
            return "Please specify the space name or run `USE <space_name>` first."
        space = space.strip()

        tags_schema, edge_types_schema, relationship_samples = [], [], []
        for tag in self._execute("SHOW TAGS").column_values("Name"):
            tag_name = tag.cast()
            tag_schema = {"tag": tag_name, "properties": []}
            r = self._execute(f"DESCRIBE TAG `{tag_name}`")
            props, types, comments = (
                r.column_values("Field"),
                r.column_values("Type"),
                r.column_values("Comment"),
            )
            for i in range(r.row_size()):
                # back compatible with old version of nebula-python
                property_defination = (
                    (props[i].cast(), types[i].cast())
                    if comments[i].is_empty()
                    else (props[i].cast(), types[i].cast(), comments[i].cast())
                )
                tag_schema["properties"].append(property_defination)
            tags_schema.append(tag_schema)
        for edge_type in self._execute("SHOW EDGES").column_values("Name"):
            edge_type_name = edge_type.cast()
            edge_schema = {"edge": edge_type_name, "properties": []}
            r = self._execute(f"DESCRIBE EDGE `{edge_type_name}`")
            props, types, comments = (
                r.column_values("Field"),
                r.column_values("Type"),
                r.column_values("Comment"),
            )
            for i in range(r.row_size()):
                # back compatible with old version of nebula-python
                property_defination = (
                    (props[i].cast(), types[i].cast())
                    if comments[i].is_empty()
                    else (props[i].cast(), types[i].cast(), comments[i].cast())
                )
                edge_schema["properties"].append(property_defination)
            edge_types_schema.append(edge_schema)

            # build sample edge
            sample_edge = self._execute(
                rel_query_sample_edge.render(edge_type=edge_type_name)
            ).column_values("sample_edge")
            if len(sample_edge) == 0:
                continue
            src_id, dst_id = sample_edge[0].cast()
            r = self._execute(
                rel_query_edge_type.render(
                    edge_type=edge_type_name, src_id=src_id, dst_id=dst_id
                )
            )
            if (
                len(r.column_values("src_tag")) == 0
                or len(r.column_values("dst_tag")) == 0
            ):
                continue
            src_tag, dst_tag = (
                r.column_values("src_tag")[0].cast(),
                r.column_values("dst_tag")[0].cast(),
            )
            relationship_samples.append(
                {
                    "src_tag": src_tag,
                    "dst_tag": dst_tag,
                    "edge_type": edge_type_name,
                }
            )

        # Create a graph of relationship_samples
        # The nodes are tags, with their properties schema as attributes
        # The edges are relationship_samples, with their properties schema as attributes

        g = Network(
            notebook=True,
            directed=True,
            cdn_resources="in_line",
            height="500px",
            width="100%",
            bgcolor="#002B36",
            font_color="#93A1A1",
            neighborhood_highlight=True,
        )
        g_nx = nx.MultiDiGraph()
        for tag_schema in tags_schema:
            tag_name = tag_schema["tag"]
            g.add_node(
                tag_name,
                label=tag_name,
                title=str(tag_schema),
                color=get_color(tag_name),
            )
            g_nx.add_node(tag_name, **tag_schema)

        for edge_schema in relationship_samples:
            src_tag, dst_tag, edge_type = (
                edge_schema["src_tag"],
                edge_schema["dst_tag"],
                edge_schema["edge_type"],
            )
            g.add_edge(src_tag, dst_tag, label=edge_type, title=str(edge_schema))
            g_nx.add_edge(src_tag, dst_tag, **edge_schema)

        g.repulsion(
            node_distance=90,
            central_gravity=0.2,
            spring_length=200,
            spring_strength=0.05,
            damping=0.09,
        )
        # g.show_buttons(filter_='physics')
        # return g.show("nebulagraph_draw.html", notebook=True)
        g_html_string = g.generate_html("nebulagraph_schema.html")
        with open("nebulagraph_schema.html", "w", encoding="utf-8") as f:
            f.write(g_html_string)
        # detect if we are in colab or not
        try:
            if "google.colab" in str(get_ipython()):
                display(HTML(g_html_string))
            else:
                display(
                    IFrame(src="nebulagraph_schema.html", width="100%", height="500px")
                )
        except Exception as e:
            print(f"[WARN]: failed to display the graph\n { e }")
            try:
                display(
                    IFrame(src="nebulagraph_schema.html", width="100%", height="500px")
                )
            except Exception as e:
                print(f"[WARN]: failed to display the graph\n { e }")

        return g

    def render_pd_item(self, g, g_nx, item):
        # g is pyvis graph
        # g_nx is networkx graph

        if isinstance(item, Node):
            node_id = str(item.get_id().cast())
            tags = item.tags()  # list of strings
            props_raw = dict()
            for tag in tags:
                props_raw.update(item.properties(tag))
            props = {
                k: str(v.cast()) if hasattr(v, "cast") else str(v)
                for k, v in props_raw.items()
            }

            if "name" in props:
                label = props["name"]
            else:
                label = f"tag: {tags}, id: {node_id}"
                for k in props:
                    if "name" in str(k).lower():
                        label = props[k]
                        break
            if "id" not in props:
                props["id"] = node_id

            g.add_node(node_id, label=label, title=str(props), color=get_color(node_id))

            # networkx
            if len(tags) > 1:
                g_nx.add_node(node_id, type=tags[0], **props)
            else:
                g_nx.add_node(node_id, **props)
        elif isinstance(item, Relationship):
            src_id = str(item.start_vertex_id().cast())
            dst_id = str(item.end_vertex_id().cast())
            edge_name = item.edge_name()
            props_raw = item.properties()
            props = {
                k: str(v.cast()) if hasattr(v, "cast") else str(v)
                for k, v in props_raw.items()
            }
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
            props_str_list: List[str] = []
            for k in props:
                if len(props_str_list) >= 1:
                    break
                props_str_list.append(f"{truncate(k, 7)}: {truncate(str(props[k]), 8)}")
            props_str = "\n".join(props_str_list)

            label = f"{props_str}\n{edge_name}" if props else edge_name
            g.add_edge(src_id, dst_id, label=label, title=str(props))
            # networkx
            props["edge_type"] = edge_name
            g_nx.add_edge(src_id, dst_id, **props)

        elif isinstance(item, PathWrapper):
            for node in item.nodes():
                self.render_pd_item(g, g_nx, node)
            for edge in item.relationships():
                self.render_pd_item(g, g_nx, edge)

        elif isinstance(item, list):
            for it in item:
                self.render_pd_item(g, g_nx, it)

    @line_cell_magic
    @magic_arguments()
    @argument(
        "--header",
        action="store_true",
        help="Specify if the CSV file contains a header row",
    )
    @argument("-n", "--space", type=str, help="Space name")
    @argument("-s", "--source", type=str, help="File path or URL to the CSV file")
    @argument("-t", "--tag", type=str, help="Tag name for vertices")
    @argument("--vid", type=int, help="Vertex ID column index")
    @argument("-e", "--edge", type=str, help="Edge type name")
    @argument("--src", type=int, help="Source vertex ID column index")
    @argument("--dst", type=int, help="Destination vertex ID column index")
    @argument("--rank", type=int, help="Rank column index", default=None)
    @argument(
        "--props",
        type=str,
        help="Property mapping, comma-separated column indexes",
        default=None,
    )
    @argument(
        "-b", "--batch", type=int, help="Batch size for data loading", default=256
    )
    def ng_load(self, line, cell=None, local_ns={}):
        """
        Load data from CSV file into NebulaGraph as vertices or edges

        Examples:
        %ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer
        %ng_load --source follow_with_rank.csv --edge follow --src 0 --dst 1 --props 2:degree --rank 3 --space basketballplayer
        %ng_load --source follow.csv --edge follow --src 0 --dst 1 --props 2:degree --space basketballplayer

        #actor.csv
        "player999","Tom Hanks",30
        "player1000","Tom Cruise",40

        #follow_with_rank.csv
        "player999","player1000",50,1
        """
        if self.connection_pool is None:
            print(
                "Please connect to NebulaGraph first using %ngql magic before using ng_load"
                "\nExample: %ngql --address 127.0.0.1 --port 9669 --user root --password nebula"
            )
            return

        try:
            import requests
            import pandas as pd
            from io import StringIO
        except ImportError:
            raise ImportError(
                "Please install requests and pandas to use ng_load"
                " magic: %pip3 install requests pandas"
            )

        args = parse_argstring(self.ng_load, line)

        # Check if space is specified
        if args.space is None:
            print("Please specify the space name using --space")
            return
        space = args.space

        # Inspect space to get Vid Type
        r = self._execute(f"DESC SPACE `{space}`")
        try:
            assert len(r.column_values("Vid Type")) == 1, "Space may not exist"
            vid_type = r.column_values("Vid Type")[0].cast()
        except Exception as e:
            raise ValueError(
                f"Failed to get Vid Type from space '{self.space}', error: {e}"
            )

        vid_length = 0
        if "FIXED_STRING" in vid_type:
            vid_length = int(vid_type.split("(")[1].split(")")[0])
        is_vid_int = vid_length == 0

        # Validate required arguments
        if not args.tag and not args.edge:
            print(
                "Missing required argument: --tag tag_name for vertex loading or --edge edge_type for edge loading"
            )
            return

        # If with header
        with_header = args.header

        # Load CSV from file or URL
        if args.source.startswith("http://") or args.source.startswith("https://"):
            response = requests.get(args.source)
            csv_string = response.content.decode("utf-8")
            df = pd.read_csv(StringIO(csv_string), header=0 if with_header else None)
        else:
            df = pd.read_csv(args.source, header=0 if with_header else None)

        # Build schema type map for tag or edge type
        prop_schema_map = {}
        DESC_TYPE = "TAG" if args.tag else "EDGE"
        DESC_TARGET = args.tag if args.tag else args.edge
        r = self._execute(f"USE {space}; DESCRIBE {DESC_TYPE} `{DESC_TARGET}`")
        props, types, nullable = (
            r.column_values("Field"),
            r.column_values("Type"),
            r.column_values("Null"),
        )
        for i in range(r.row_size()):
            # back compatible with old version of nebula-python
            prop_schema_map[props[i].cast()] = {
                "type": types[i].cast(),
                "nullable": nullable[i].cast() == "YES",
            }

        # Process properties mapping
        props_mapping = (
            {int(k): v for k, v in (prop.split(":") for prop in args.props.split(","))}
            if args.props
            else {}
        )
        # Values of props_mapping are property names they should be strings
        # Keys of props_mapping are column indexes they should be integers
        for k, v in props_mapping.items():
            if not isinstance(k, int):
                print(
                    f"ERROR during prop mapping validation: Key '{k}' in property mapping is not an integer"
                )
                return
            if not isinstance(v, str):
                print(
                    f"ERROR during prop mapping validation: Value '{v}' in property mapping is not a string"
                )
                return
            if k >= len(df.columns) or k < 0:
                print(
                    f"ERROR during prop mapping validation: Key '{k}' in property mapping is out of range: 0-{len(df.columns)-1}"
                )
                return

        with_props = True if props_mapping else False

        # Validate props_mapping against schema
        matched = True
        for i, prop in props_mapping.items():
            if prop not in prop_schema_map:
                print(
                    f"Error: Property '{prop}' not found in schema for {DESC_TYPE} '{args.tag}'"
                )
                matched = False
        for prop in prop_schema_map:
            # For not nullable properties, check if they are in props_mapping
            if (
                not prop_schema_map[prop]["nullable"]
                and prop not in props_mapping.values()
            ):
                print(
                    f"Error: Property '{prop}' is not nullable and not found in property mapping"
                )
                matched = False

        if not matched:
            print("Error: Property mapping does not match schema")
            return

        if args.rank is not None:
            with_rank = True
        else:
            with_rank = False

        # Prepare data for loading
        if args.tag and not args.edge:
            if args.vid is None:
                raise ValueError("Missing required argument: --vid for vertex ID")
            # Process properties mapping
            vertex_data_columns = ["___vid"] + [
                props_mapping[i] for i in range(len(df.columns)) if i in props_mapping
            ]
            vertex_data = df.iloc[:, [args.vid] + list(props_mapping.keys())]
            vertex_data.columns = vertex_data_columns
            # Here you would load vertex_data into NebulaGraph under the specified tag and space
            print(
                f"Parsed {len(vertex_data)} vertices '{args.space}' for tag '{args.tag}' in memory"
            )
        elif args.edge and not args.tag:
            if args.src is None or args.dst is None:
                raise ValueError(
                    "Missing required arguments: --src and/or --dst for edge source and destination IDs"
                )
            # Process properties mapping
            edge_data_columns = ["___src", "___dst"] + [
                props_mapping[i] for i in range(len(df.columns)) if i in props_mapping
            ]
            edge_data_indices = [args.src, args.dst] + list(props_mapping.keys())
            if with_rank:
                edge_data_columns += ["___rank"]
                edge_data_indices += [args.rank]
            edge_data = df.iloc[:, edge_data_indices]
            edge_data.columns = edge_data_columns
            # Here you would load edge_data into NebulaGraph under the specified edge type and space
            print(
                f"Parsed {len(edge_data)} edges '{args.space}' for edge type '{args.edge}' in memory"
            )
        else:
            raise ValueError(
                "Specify either --tag for vertex loading or --edge for edge loading, not both"
            )

        # Load data into NebulaGraph
        batch_size = args.batch

        QUOTE_VID = "" if is_vid_int else '"'
        QUOTE = '"'

        if args.tag:
            # Load vertex_data into NebulaGraph under the specified tag and space
            # Now prepare INSERT query for vertices in batches
            # Example of QUERY: INSERT VERTEX t2 (name, age) VALUES "13":("n3", 12), "14":("n4", 8);

            for i in range(0, len(vertex_data), batch_size):
                batch = vertex_data.iloc[i : i + batch_size]
                query = f"INSERT VERTEX {args.tag} ({', '.join([col for col in vertex_data.columns if col != '___vid'])}) VALUES "
                for index, row in batch.iterrows():
                    vid_str = f'{QUOTE_VID}{row["___vid"]}{QUOTE_VID}'
                    prop_str = ""
                    if with_props:
                        for prop_name in props_mapping.values():
                            prop_value = row[prop_name]
                            if pd.isnull(prop_value):
                                if not prop_schema_map[prop_name]["nullable"]:
                                    raise ValueError(
                                        f"Error: Property '{prop_name}' is not nullable but received NULL value, "
                                        f"data: {row}, column: {prop_name}"
                                    )
                                prop_str += "NULL, "
                            elif prop_schema_map[prop_name]["type"] == "string":
                                prop_str += f"{QUOTE}{prop_value}{QUOTE}, "
                            else:
                                prop_str += f"{prop_value}, "
                        prop_str = prop_str[:-2]
                    query += f"{vid_str}:({prop_str}), "
                query = query[:-2] + ";"
                try:
                    result = self._execute(query)
                except Exception as e:
                    print(
                        f"INSERT Failed on row {i + index}, data: {row}, error: {result.error_msg()}"
                    )
                    return

            print(
                f"Successfully loaded {len(vertex_data)} vertices '{args.space}' for tag '{args.tag}'"
            )
        elif args.edge:
            # Load edge_data into NebulaGraph under the specified edge type and space
            # Now prepare INSERT query for edges in batches
            # Example of QUERY:
            # with_rank INSERT EDGE e1 (name, age) VALUES "13" -> "14"@1:("n3", 12), "14" -> "15"@132:("n4", 8);
            # without_rank INSERT EDGE e1 (name, age) VALUES "13" -> "14":("n3", 12), "14" -> "15":("n4", 8);

            for i in range(0, len(edge_data), batch_size):
                batch = edge_data.iloc[i : i + batch_size]
                query = f"INSERT EDGE {args.edge} ({', '.join([col for col in edge_data.columns if col not in ['___src', '___dst', '___rank']])}) VALUES "
                for index, row in batch.iterrows():
                    src_str = f'{QUOTE_VID}{row["___src"]}{QUOTE_VID}'
                    dst_str = f'{QUOTE_VID}{row["___dst"]}{QUOTE_VID}'
                    prop_str = ""
                    if with_props:
                        for prop_name in props_mapping.values():
                            prop_value = row[prop_name]
                            if pd.isnull(prop_value):
                                if not prop_schema_map[prop_name]["nullable"]:
                                    raise ValueError(
                                        f"Error: Property '{prop_name}' is not nullable but received NULL value, "
                                        f"data: {row}, column: {prop_name}"
                                    )
                                prop_str += "NULL, "
                            elif prop_schema_map[prop_name]["type"] == "string":
                                prop_str += f"{QUOTE}{prop_value}{QUOTE}, "
                            else:
                                prop_str += f"{prop_value}, "
                        prop_str = prop_str[:-2]
                    if with_rank:
                        rank_str = f"@{row['___rank']}"
                    else:
                        rank_str = ""
                    query += f"{src_str} -> {dst_str}{rank_str}:({prop_str}), "
                query = query[:-2] + ";"
                try:
                    result = self._execute(query)
                except Exception as e:
                    print(
                        f"INSERT Failed on row {i + index}, data: {row}, error: {result.error_msg()}"
                    )
                    return
