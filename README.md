![](https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/61fccff2-c9be-43a0-a26f-6f5a00b1c198)


[![for NebulaGraph](https://img.shields.io/badge/Toolchain-NebulaGraph-blue)](https://github.com/vesoft-inc/nebula) [![Jupyter](https://img.shields.io/badge/Jupyter-Supported-brightgreen)](https://github.com/jupyterlab/jupyterlab) [![Docker Image](https://img.shields.io/docker/v/weygu/nebulagraph-jupyter?label=Image&logo=docker)](https://hub.docker.com/r/weygu/nebulagraph-jupyter) [![Docker Extension](https://img.shields.io/badge/Docker-Extension-blue?logo=docker)](https://hub.docker.com/extensions/weygu/nebulagraph-dd-ext) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/wey-gu/jupyter_nebulagraph?label=Version)](https://github.com/wey-gu/jupyter_nebulagraph/releases)
[![pypi-version](https://img.shields.io/pypi/v/jupyter_nebulagraph)](https://pypi.org/project/jupyter_nebulagraph/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wey-gu/jupyter_nebulagraph/blob/main/docs/get_started.ipynb)
[![Documentation](https://img.shields.io/badge/docs-Read%20The%20Docs-blue)](https://jupyter-nebulagraph.readthedocs.io/)


https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/10135264-77b5-4d3c-b68f-c5810257feeb

`jupyter_nebulagraph`, formerly `ipython-ngql`, is a Python package that simplifies the process of connecting to NebulaGraph from Jupyter Notebooks or iPython environments. It enhances the user experience by streamlining the creation, debugging, and sharing of Jupyter Notebooks. With `jupyter_nebulagraph`, users can effortlessly connect to NebulaGraph, load data, execute queries, visualize results, and fine-tune query outputs, thereby boosting collaborative efforts and productivity.

![](https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/b3d9ca07-2eb1-45ae-949b-543f58a57760)

## Getting Started

Explore the capabilities of `jupyter_nebulagraph` by trying it on [Google Colab](https://colab.research.google.com/github/wey-gu/jupyter_nebulagraph/blob/main/docs/get_started.ipynb), and the equivalent Jupyter Notebook is available in Docs [here](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started_docs/).

For a comprehensive guide, visit the [official documentation](https://jupyter-nebulagraph.readthedocs.io/).

| Feature | Cheat Sheet | Example | Command Documentation |
| ------- | ----------- | --------- | ---------------------- |
| Connect | `%ngql --address 127.0.0.1 --port 9669 --user user --password password` | [Connect](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started_docs/#connect-to-nebulagraph) | [`%ngql`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ngql/#connect-to-nebulagraph) |
| Load Data from CSV | `%ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer` | [Load Data](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started_docs/#load-data-from-csv) | [`%ng_load`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_load/) |
| Query Execution | `%ngql MATCH p=(v:player{name:"Tim Duncan"})-->(v2:player) RETURN p;`| [Query Execution](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started_docs/#query) | [`%ngql` or `%%ngql`(multi-line)](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ngql/#make-queries) |
| Result Visualization | `%ng_draw` | [Draw Graph](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw/) | [`%ng_draw`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw/) |
| Draw Schema | `%ng_draw_schema` | [Draw Schema](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw_schema/) | [`%ng_draw_schema`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw_schema/) |
| Tweak Query Result | `df = _` to get last query result as `pd.dataframe` or [`ResultSet`](https://github.com/vesoft-inc/nebula-python/blob/master/nebula3/data/ResultSet.py) | [Tweak Result](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started_docs/#result-handling) | [Configure `ngql_result_style`](https://jupyter-nebulagraph.readthedocs.io/en/latest/configurations/#configure-ngql_result_style) |


<details>
<summary>Click to see more!</summary>

### Installation

`jupyter_nebulagraph` could be installed either via pip or from this git repo itself.

> Install via pip

```bash
pip install jupyter_nebulagraph
```

> Install inside the repo

```bash
git clone git@github.com:wey-gu/jupyter_nebulagraph.git
cd jupyter_nebulagraph
python setup.py install
```

### Load it in Jupyter Notebook or iPython

```python
%load_ext ngql
```

### Connect to NebulaGraph

Arguments as below are needed to connect a NebulaGraph DB instance:

| Argument               | Description                              |
| ---------------------- | ---------------------------------------- |
| `--address` or `-addr` | IP address of the NebulaGraph Instance   |
| `--port` or `-P`       | Port number of the NebulaGraph Instance  |
| `--user` or `-u`       | User name                                |
| `--password` or `-p`   | Password                                 |

Below is an exmple on connecting to `127.0.0.1:9669` with username: "user" and password: "password".

```python
%ngql --address 127.0.0.1 --port 9669 --user user --password password
```

### Make Queries

Now two kind of iPtython Magics are supported:

Option 1: The one line stype with `%ngql`:

```python
%ngql USE basketballplayer;
%ngql MATCH (v:player{name:"Tim Duncan"})-->(v2:player) RETURN v2.player.name AS Name;
```

Option 2: The multiple lines stype with `%%ngql `

```python
%%ngql
SHOW TAGS;
SHOW HOSTS;
```

### Query String with Variables

`jupyter_nebulagraph` supports taking variables from the local namespace, with the help of [Jinja2](https://jinja.palletsprojects.com/) template framework, it's supported to have queries like the below example.

The actual query string should be `GO FROM "Sue" OVER owns_pokemon ...`, and `"{{ trainer }}"` was renderred as `"Sue"` by consuming the local variable `trainer`:

```python
In [8]: vid = "player100"

In [9]: %%ngql
   ...: MATCH (v)<-[e:follow]- (v2)-[e2:serve]->(v3)
   ...:   WHERE id(v) == "{{ vid }}"
   ...: RETURN v2.player.name AS FriendOf, v3.team.name AS Team LIMIT 3;
Out[9]:   RETURN v2.player.name AS FriendOf, v3.team.name AS Team LIMIT 3;
FriendOf	Team
0	LaMarcus Aldridge	Trail Blazers
1	LaMarcus Aldridge	Spurs
2	Marco Belinelli	Warriors
```

### Draw query results

Just call `%ng_draw` after queries with graph data.

```python
# one query
%ngql GET SUBGRAPH 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;
%ng_draw

# another query
%ngql match p=(:player)-[]->() return p LIMIT 5
%ng_draw
```

![](https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/b3d9ca07-2eb1-45ae-949b-543f58a57760)

### Draw Graph Schema

```python
%ng_draw_schema
```

![](https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/81fd71b5-61e7-4c65-93be-c2f4e507611b)

### Load Data from CSV

It's supported to load data from a CSV file into NebulaGraph with the help of `ng_load_csv` magic.

For example, to load data from a CSV file `actor.csv` into a space `basketballplayer` with tag `player` and vid in column `0`, and props in column `1` and `2`:

```csv
"player999","Tom Hanks",30
"player1000","Tom Cruise",40
"player1001","Jimmy X",33
```

Just run the below line:

```python
%ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer
```

Some other examples:

```python
# load CSV from a URL
%ng_load --source https://github.com/wey-gu/jupyter_nebulagraph/raw/main/examples/actor.csv --tag player --vid 0 --props 1:name,2:age --space demo_basketballplayer
# with rank column
%ng_load --source follow_with_rank.csv --edge follow --src 0 --dst 1 --props 2:degree --rank 3 --space basketballplayer
# without rank column
%ng_load --source follow.csv --edge follow --src 0 --dst 1 --props 2:degree --space basketballplayer
```

### Tweak Query Result

By default, the query result is a Pandas Dataframe, and we could access that by read from variable `_`.

```python
In [1]: %ngql MATCH (v:player{name:"Tim Duncan"})-->(v2:player) RETURN v2.player.name AS Name;

In [2]: df = _
```

It's also configurable to have the result in raw ResultSet, to enable handy NebulaGraph Python App Development.

See more via [Docs: Result Handling](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started_docs/#result-handling)

### CheatSheet

If you find yourself forgetting commands or not wanting to rely solely on the cheat sheet, remember this one thing: seek help through the help command!

```python
%ngql help
```

</details>

## Acknowledgments ♥️

- Inspiration for this project comes from [ipython-sql](https://github.com/catherinedevlin/ipython-sql), courtesy of [Catherine Devlin](https://catherinedevlin.blogspot.com/).
- Graph visualization features are enabled by [pyvis](https://github.com/WestHealth/pyvis), a project by [WestHealth](https://github.com/WestHealth).
- Generous sponsorship and support provided by [Vesoft Inc.](https://www.vesoft.com/) and the [NebulaGraph community](https://github.com/vesoft-inc/nebula).
