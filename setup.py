import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="teleport",
    version="0.0.1",
    author="Alexander Henne",
    author_email="alexander@henne.nu",
    description="Unofficial AmpliFi Teleport desktop client",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/alexanderhenne/teleport",
    project_urls={
        "Bug Tracker": "https://github.com/alexanderhenne/teleport/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)
