
`ipython-ngql` is a Python package that enhances your ability to connect to NebulaGraph from your Jupyter Notebook or iPython. It simplifies the process for data scientists to create, debug, and share all-in-one Jupyter Notebooks with NebulaGraph interaction embedded to facilitate easier collaboration.

`ipython-ngql` draws inspiration from [ipython-sql](https://github.com/catherinedevlin/ipython-sql), created by [Catherine Devlin](https://catherinedevlin.blogspot.com/)

![](https://user-images.githubusercontent.com/1651790/236798634-8ccb3b5c-8a4f-4834-b602-10eeb2678bc8.png)

![](https://user-images.githubusercontent.com/1651790/236798238-49dd59c9-0827-4a86-b714-fb195e6be4b9.png)


## Get Started

### Installation

`ipython-ngql` could be installed either via pip or from this git repo itself.

> Install via pip

```bash
pip install ipython-ngql
```

> Install inside the repo

```bash
git clone git@github.com:wey-gu/ipython-ngql.git
cd ipython-ngql
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

> There will be other options in future, i.e. from a `.ngql` file.

### Query String with Variables

`ipython-ngql` supports taking variables from the local namespace, with the help of [Jinja2](https://jinja.palletsprojects.com/) template framework, it's supported to have queries like the below example.

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

![](https://user-images.githubusercontent.com/1651790/236797874-c142cfd8-b0de-4689-95ef-1da386e137d3.png)

### Configure `ngql_result_style`

By default, `ipython-ngql` will use pandas dataframe as output style to enable more human-readable output, while it's supported to use the raw thrift data format that comes from the `nebula3-python` itself.

This can be done ad-hoc with below one line:

```python
%config IPythonNGQL.ngql_result_style="raw"
```

After the above line is executed, the output will be like this:

```python
ResultSet(ExecutionResponse(
    error_code=0,
    latency_in_us=2844,
    data=DataSet(
        column_names=[b'Trainer_Name'],
        rows=[Row(
            values=[Value(
                sVal=b'Tom')]),
...
        Row(
            values=[Value(
                sVal=b'Wey')])]),
    space_name=b'pokemon_club'))
```

The result are always stored in variable `_` in Jupyter Notebook, thus, to tweak the result, just refer a new var to it like:

```python
In [1] : %config IPythonNGQL.ngql_result_style="raw"

In [2] : %%ngql USE pokemon_club;
    ...: GO FROM "Tom" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id
    ...: | GO FROM $-.pokemon_id OVER owns_pokemon REVERSELY YIELD owns_pokemon._dst AS Trainer_Name;
    ...:
    ...:
Out[3]:
ResultSet(ExecutionResponse(
    error_code=0,
    latency_in_us=3270,
    data=DataSet(
        column_names=[b'Trainer_Name'],
        rows=[Row(
            values=[Value(
                sVal=b'Tom')]),
...
        Row(
            values=[Value(
                sVal=b'Wey')])]),
    space_name=b'pokemon_club'))

In [4]: r = _

In [5]: r.column_values(key='Trainer_Name')[0].cast()
Out[5]: 'Tom'
```

### Get Help

Don't remember anything or even relying on the cheatsheet here, oen takeaway for you: the help!

```python
In [1]: %ngql help

```

### Examples

#### Jupyter Notebook

Please refer here:https://github.com/wey-gu/ipython-ngql/blob/main/examples/get_started.ipynb

#### iPython

```python
In [1]: %load_ext ngql

In [2]: %ngql --address 192.168.8.128 --port 9669 --user root --password nebula
Connection Pool Created
Out[2]: 
                        Name
0           basketballplayer
1  demo_movie_recommendation
2                        k8s
3                       test

In [3]: %ngql USE basketballplayer;
   ...: %ngql MATCH (v:player{name:"Tim Duncan"})-->(v2:player) RETURN v2.player.name AS Name;
Out[3]: 
            Name
0    Tony Parker
1  Manu Ginobili
```

