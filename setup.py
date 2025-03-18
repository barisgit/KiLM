from setuptools import setup, find_packages
import re

def get_version():
    """Get version from __init__.py."""
    with open("kicad_lib_manager/__init__.py", "r") as f:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
        if version_match:
            return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

setup(
    name="kilm",
    version=get_version(),
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