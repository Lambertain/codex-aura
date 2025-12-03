#!/usr/bin/env python3
"""Main CLI entry point for codex-aura."""

import argparse


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Code context mapping for AI agents")
    parser.add_argument("--version", action="version", version="codex-aura 0.1.0")

    parser.parse_args()

    # For now, just print a message
    print("Welcome to codex-aura!")
    print("Code context mapping for AI agents")
    print("Use --help for more information")


if __name__ == "__main__":
    main()
