
## Draw query results

To render the graph, just call `%ng_draw` after queries with graph data.

```python
# one query
%ngql GET SUBGRAPH 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;
%ng_draw

# another query
%ngql match p=(:player)-[]->() return p LIMIT 5
%ng_draw
```

![](https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/b3d9ca07-2eb1-45ae-949b-543f58a57760)

And the result will be displayed as below:

<div class="ng_draw" style="width: 90%; height: 500px;">
    <iframe src="../../assets/nebulagraph.html" style="width: 100%; height: 100%;"></iframe>
</div>