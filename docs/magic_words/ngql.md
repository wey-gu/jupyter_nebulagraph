
## Connect to NebulaGraph

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

## Make Queries

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

## Query String with Variables

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

## Draw query results

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