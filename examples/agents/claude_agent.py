#!/usr/bin/env python3
"""Example Claude agent integration with Codex Aura for bug fixing."""

import os
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from codex_aura import CodexAura


def fix_bug_with_claude(
    repo_path: str,
    bug_description: str,
    file_hint: Optional[str] = None
) -> str:
    """
    Fix a bug using Claude with Codex Aura context.

    Args:
        repo_path: Path to the repository
        bug_description: Description of the bug to fix
        file_hint: Optional hint about which file contains the bug

    Returns:
        Claude's response with the fix
    """
    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get context around the bug
    context = ca.get_context(
        task=bug_description,
        entry_points=[file_hint] if file_hint else None,
        max_tokens=6000
    )

    # Initialize Anthropic client
    anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Build prompt
    prompt = f"""You are a senior developer fixing a bug.

## Bug Description
{bug_description}

## Relevant Code Context
{context.to_prompt(format="markdown")}

## Instructions
1. Analyze the code and identify the bug
2. Provide a fix with explanation
3. Suggest tests to prevent regression

Respond with the fix."""

    # Call Claude
    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def fix_bug_with_claude_xml(
    repo_path: str,
    bug_description: str,
    file_hint: Optional[str] = None
) -> str:
    """
    Fix a bug using Claude with XML-formatted context.

    Args:
        repo_path: Path to the repository
        bug_description: Description of the bug to fix
        file_hint: Optional hint about which file contains the bug

    Returns:
        Claude's response with the fix
    """
    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get context around the bug
    context = ca.get_context(
        task=bug_description,
        entry_points=[file_hint] if file_hint else None,
        max_tokens=6000
    )

    # Initialize Anthropic client
    anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Build prompt with XML context
    prompt = f"""You are a senior developer fixing a bug.

## Bug Description
{bug_description}

## Code Context (XML)
{context.to_prompt(format="xml", include_edges=True)}

## Instructions
1. Analyze the XML context and identify the bug
2. Provide a fix with explanation
3. Suggest tests to prevent regression

Respond with the fix."""

    # Call Claude
    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


if __name__ == "__main__":
    # Example usage
    repo_path = "."  # Current directory
    bug_description = "JWT tokens are not validated correctly"
    file_hint = "src/auth/jwt.py"

    print("Fixing bug with Claude using markdown context...")
    try:
        fix = fix_bug_with_claude(
            repo_path=repo_path,
            bug_description=bug_description,
            file_hint=file_hint
        )
        print("Claude's response:")
        print(fix)
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "="*50 + "\n")

    print("Fixing bug with Claude using XML context...")
    try:
        fix_xml = fix_bug_with_claude_xml(
            repo_path=repo_path,
            bug_description=bug_description,
            file_hint=file_hint
        )
        print("Claude's response:")
        print(fix_xml)
    except Exception as e:
        print(f"Error: {e}")