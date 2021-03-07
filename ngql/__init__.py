from .magic import IPythonNGQL


def load_ipython_extension(ipython):
    ipython.register_magics(IPythonNGQL)
