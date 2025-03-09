from setuptools import setup, find_packages

setup(
    name="kicad-lib-manager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",  # For CLI interface
        "pyyaml>=6.0",  # For YAML parsing
        "pathlib>=1.0.1",  # For cross-platform path handling
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
    author="Your Name",
    author_email="your.email@example.com",
    description="Tools for managing KiCad libraries",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/kicad-lib-manager",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
) 