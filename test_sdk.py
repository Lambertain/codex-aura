#!/usr/bin/env python3
"""Test script for Codex Aura SDK."""

import sys
import os

# Add src to path
sys.path.insert(0, 'src')

def test_sdk():
    print("Testing Codex Aura SDK...")

    try:
        from codex_aura import CodexAura, Context, ImpactAnalysis
        print("✓ Imports successful")

        # Test local mode
        repo_path = os.path.join(os.getcwd(), 'examples', 'simple_project')
        print(f"Testing with repo: {repo_path}")

        ca = CodexAura(repo_path=repo_path)
        print("✓ Client initialized")

        # Test analysis
        graph_id = ca.analyze()
        print(f"✓ Analysis completed: {graph_id}")

        # Test context - use file path instead of function name
        context = ca.get_context(
            task="Test task",
            entry_points=["main.py"]
        )
        print(f"✓ Context retrieved: {len(context.context_nodes)} nodes")

        # Test impact
        impact = ca.analyze_impact(["main.py"])
        print(f"✓ Impact analyzed: {len(impact.affected_files)} affected files")

        # Test prompt formatting
        prompt = context.to_prompt()
        print(f"✓ Prompt generated: {len(prompt)} characters")

        print("All tests passed! ✓")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = test_sdk()
    sys.exit(0 if success else 1)