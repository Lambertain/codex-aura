#!/usr/bin/env python3
"""Benchmark script to measure token savings with Codex Aura."""

import os
from pathlib import Path
from typing import List, Dict, Any

import tiktoken
from codex_aura import CodexAura


def count_all_python_files(repo_path: str, enc: tiktoken.Encoding) -> int:
    """
    Count total tokens in all Python files in the repository.

    Args:
        repo_path: Path to the repository
        enc: Tiktoken encoding to use

    Returns:
        Total token count
    """
    total_tokens = 0
    repo_path = Path(repo_path)

    for py_file in repo_path.glob("**/*.py"):
        try:
            with py_file.open('r', encoding='utf-8') as f:
                content = f.read()
                tokens = len(enc.encode(content))
                total_tokens += tokens
        except (UnicodeDecodeError, OSError):
            continue

    return total_tokens


def benchmark_token_savings(repo_path: str, tasks: List[str]) -> List[Dict[str, Any]]:
    """
    Benchmark token savings for different tasks.

    Args:
        repo_path: Path to the repository
        tasks: List of task descriptions

    Returns:
        List of benchmark results
    """
    ca = CodexAura(repo_path=repo_path)
    enc = tiktoken.get_encoding("cl100k_base")

    results = []

    for task in tasks:
        # Full repo context
        full_repo_tokens = count_all_python_files(repo_path, enc)

        # Codex Aura context
        context = ca.get_context(task=task, max_tokens=8000)
        ca_tokens = len(enc.encode(context.to_prompt()))

        savings = (1 - ca_tokens / full_repo_tokens) * 100

        results.append({
            "task": task,
            "full_repo_tokens": full_repo_tokens,
            "codex_aura_tokens": ca_tokens,
            "savings_percent": savings
        })

    return results


def print_markdown_table(results: List[Dict[str, Any]]) -> str:
    """Generate markdown table from results."""
    lines = [
        "| Task                  | Full Repo | Codex Aura | Savings |",
        "|-----------------------|-----------|------------|---------|"
    ]

    for result in results:
        task = result["task"][:20] + "..." if len(result["task"]) > 20 else result["task"]
        full_repo = f"{result['full_repo_tokens']:,}"
        ca_tokens = f"{result['codex_aura_tokens']:,}"
        savings = f"{result['savings_percent']:.1f}%"

        lines.append(f"| {task:<21} | {full_repo:>9} | {ca_tokens:>10} | {savings:>7} |")

    return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    repo_path = "."  # Current directory
    tasks = [
        "Fix auth bug",
        "Add user endpoint",
        "Implement caching",
        "Database migration"
    ]

    print("Benchmarking token savings...")
    try:
        results = benchmark_token_savings(repo_path=repo_path, tasks=tasks)

        print("\nResults:")
        print(print_markdown_table(results))

        # Summary
        avg_savings = sum(r["savings_percent"] for r in results) / len(results)
        print(f"\nAverage savings: {avg_savings:.1f}%")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()