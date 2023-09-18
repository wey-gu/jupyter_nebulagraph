import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ipython-ngql",
    version="0.7.2",
    author="Wey Gu",
    author_email="weyl.gu@gmail.com",
    description="Jupyter and iPython extension for NebulaGraph",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wey-gu/ipython-ngql",
    project_urls={
        "Bug Tracker": "https://github.com/wey-gu/ipython-ngql/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "Jinja2",
        "nebula3-python>=3.4.0",
        "pandas",
    ],
)
