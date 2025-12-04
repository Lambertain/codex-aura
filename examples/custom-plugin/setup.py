"""Setup script for custom plugin example."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="codex-aura-custom-plugin",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Custom plugin example for Codex Aura",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/codex-aura-custom-plugin",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        "codex-aura>=0.1.0",
    ],
    entry_points={
        "codex_aura.plugins.context": [
            "custom_context = codex_aura_custom_plugin.context:CustomContextPlugin",
        ],
        "codex_aura.plugins.impact": [
            "custom_impact = codex_aura_custom_plugin.impact:CustomImpactPlugin",
        ],
    },
    extras_require={
        "dev": ["pytest>=7.0", "black", "isort", "flake8"],
    },
)