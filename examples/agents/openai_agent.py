#!/usr/bin/env python3
"""Example OpenAI agent integration with Codex Aura for code review."""

import os
from typing import List

from openai import OpenAI
from codex_aura import CodexAura


def code_review_with_gpt(repo_path: str, pr_files: List[str]) -> str:
    """
    Perform code review using GPT with Codex Aura context.

    Args:
        repo_path: Path to the repository
        pr_files: List of changed file paths

    Returns:
        GPT's code review response
    """
    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get impact of changed files
    impact = ca.analyze_impact(pr_files)

    # Get context for affected area
    context = ca.get_context(
        task="Code review for changes",
        entry_points=pr_files,
        depth=1,
        max_tokens=4000
    )

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""Review these code changes.

Changed files: {pr_files}
Affected files: {impact.affected_files}

Context:
{context.to_prompt()}

Provide:
1. Potential issues
2. Suggestions for improvement
3. Security concerns if any"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    # Example usage
    repo_path = "."  # Current directory
    pr_files = ["src/auth/jwt.py", "tests/test_auth.py"]

    print("Performing code review with GPT...")
    try:
        review = code_review_with_gpt(
            repo_path=repo_path,
            pr_files=pr_files
        )
        print("GPT's code review:")
        print(review)
    except Exception as e:
        print(f"Error: {e}")