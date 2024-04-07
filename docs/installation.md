
## Installation

`jupyter_nebulagraph` should be installed via pip.

```bash
pip install jupyter_nebulagraph
```

> Note: if you are doing this in a Jupyter Notebook, you can use the `!` or `%` prefix to run shell commands directly in the notebook.

```bash
%pip install jupyter_nebulagraph
```

## Load it in Jupyter Notebook or iPython

In each Jupyter Notebook or iPython environment, you need to load the extension before using it.

```python
%load_ext ngql
```

## Appendix

### NebulaGraph Installation Options

But how to get a NebulaGraph instance to connect to? Here are some options:

- [Documents](https://docs.nebula-graph.io/), to go through the official installation guide for NebulaGraph.
- [Docker Compose](https://github.com/vesoft-inc/nebula-docker-compose), if you are comfortable to play with Docker on single server.
- [NebulaGraph-Lite](https://github.com/nebula-contrib/nebulagraph-lite), install on Linux or Colab with `pip install` for ad-hoc playground.
- [Docker Extension](https://github.com/nebula-contrib/nebulagraph-docker-ext), one-click on Docker Desktop(macOS, windows) on desktop machines, in GUI flavor, jupyter environment included.
- [nebula-up](https://github.com/nebula-contrib/nebula-up), one-liner test env installer on single server, support studio, dashboard, nebulagraph algorithm, exchange etc, all-in-one.
- [Nebula-Operator-KinD](https://github.com/nebula-contrib/nebula-operator-kind), Nebula K8s Operator with K8s-in-Docker, one-liner test env with docker+k8s+nebulagrpah-operator, try NebulaGraph on K8s with ease on your single server.
