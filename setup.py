import setuptools

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setuptools.setup(
    name="pimpmyrice",
    version="0.3.2",
    author="daddodev",
    author_email="daddodev@gmail.com",
    description="The overkill rice manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/daddodev/pimpmyrice",
    project_urls={
        "Bug Tracker": "https://github.com/daddodev/pimpmyrice/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={"console_scripts": ["pimp=pimpmyrice.__main__:main"]},
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    package_data={
        "pimpmyrice": ["assets/*.json"],
    },
    python_requires=">=3.10",
    install_requires=[
        "rich",
        "docopt",
        "pyyaml",
        "jinja2",
        "requests",
        "psutil",
        "numpy",
        "pillow",
        "pydantic",
        "typing_extensions",
    ],
    extras_require={
        "dev": [
            "ruff",
            "mypy",
            "isort",
            "pytest",
            "pytest-asyncio",
            "types-requests",
            "types-PyYAML",
        ],
    },
)
