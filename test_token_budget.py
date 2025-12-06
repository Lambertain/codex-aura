#!/usr/bin/env python3
"""Simple test for token budget functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test presets directly
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("presets", "src/codex_aura/token_budget/presets.py")
    presets_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(presets_module)
    BUDGET_PRESETS = presets_module.BUDGET_PRESETS
    print("✓ Presets imported successfully")
    print(f"Available models: {list(BUDGET_PRESETS.keys())}")
    print(f"GPT-4 preset: {BUDGET_PRESETS.get('gpt-4-turbo')}")
except Exception as e:
    print(f"✗ Presets import failed: {e}")

# Test analytics directly
try:
    spec = importlib.util.spec_from_file_location("analytics", "src/codex_aura/token_budget/analytics.py")
    analytics_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analytics_module)
    BudgetAnalytics = analytics_module.BudgetAnalytics
    analytics = BudgetAnalytics()
    print("✓ BudgetAnalytics imported successfully")
except Exception as e:
    print(f"✗ BudgetAnalytics import failed: {e}")

# Test allocator directly
try:
    spec = importlib.util.spec_from_file_location("allocator", "src/codex_aura/token_budget/allocator.py")
    allocator_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(allocator_module)
    BudgetAllocator = allocator_module.BudgetAllocator
    allocator = BudgetAllocator()
    print("✓ BudgetAllocator imported successfully")
except Exception as e:
    print(f"✗ BudgetAllocator import failed: {e}")

print("Token budget module test completed.")