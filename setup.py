from setuptools import setup, find_packages

setup(
    name="kilm",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "pyyaml>=6.0",
        "pathlib>=1.0.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "kicad-lib-manager=kicad_lib_manager.cli:main",
            "kilm=kicad_lib_manager.cli:main",    
        ],
    },
    author="Blaž Aristovnik, Paxia LCC",
    author_email="blaz@paxia.co",
    description="A command-line tool for managing KiCad libraries across projects and workstations",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/barisgit/KiLM",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    ],
    python_requires=">=3.7",
) 