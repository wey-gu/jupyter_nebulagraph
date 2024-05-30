
## Draw query results

**Draw Last Query**

To render the graph, just call `%ng_draw` after queries with graph data.

```python
# one query
%ngql GET SUBGRAPH 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;
%ng_draw

# another query
%ngql match p=(:player)-[]->() return p LIMIT 5
%ng_draw
```

<img width="1142" alt="ng_draw_demo_0" src="https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/b3d9ca07-2eb1-45ae-949b-543f58a57760">

And the result will be displayed as below:

<div class="ng_draw" style="width: 90%; height: 500px;">
    <iframe src="../../assets/nebulagraph.html" style="width: 100%; height: 100%;"></iframe>
</div>

**Draw a Query**

Or `%ng_draw <one_line_query>`, `%%ng_draw <multiline_query>` instead of drawing the result of the last query.

<img width="1142" alt="ng_draw_demo_1" src="https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/a6e3b2d4-0320-4287-bd2f-537cff77c1de">

One line query:

```python
%ng_draw GET SUBGRAPH 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;
```

Multiple lines query:

```python
%%ng_draw
MATCH path_0=(n)--() WHERE id(n) == "p_0"
OPTIONAL MATCH path_1=(n)--()--()
RETURN path_0, path_1
```