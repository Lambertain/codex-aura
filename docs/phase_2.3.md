# 📋 Phase 2.3: Token Budgeting & Smart Context API

---

## E5: 💰 Token Budgeting (Детальная реализация)

### E5-1: Token Counter
**Оценка:** 2h | **Приоритет:** P0

### Описание
Точный подсчёт токенов для разных LLM моделей.

### Реализация

```python
# src/codex_aura/budgeting/counter.py

import tiktoken
from functools import lru_cache
from typing import Literal

ModelName = Literal[
    "gpt-4", "gpt-4-turbo", "gpt-4o", 
    "gpt-3.5-turbo",
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    "claude-3.5-sonnet"
]

class TokenCounter:
    """
    Accurate token counting for different LLM models.
    
    Uses tiktoken for OpenAI models and approximations for others.
    """
    
    # Model to encoding mapping
    ENCODINGS = {
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "o200k_base",
        "gpt-3.5-turbo": "cl100k_base",
        # Claude uses similar tokenization to cl100k
        "claude-3-opus": "cl100k_base",
        "claude-3-sonnet": "cl100k_base",
        "claude-3-haiku": "cl100k_base",
        "claude-3.5-sonnet": "cl100k_base",
    }
    
    # Claude tokenization multiplier (slightly different from OpenAI)
    CLAUDE_MULTIPLIER = 1.05
    
    def __init__(self):
        self._encodings: dict[str, tiktoken.Encoding] = {}
    
    @lru_cache(maxsize=10)
    def _get_encoding(self, model: ModelName) -> tiktoken.Encoding:
        """Get or create encoding for model."""
        encoding_name = self.ENCODINGS.get(model, "cl100k_base")
        return tiktoken.get_encoding(encoding_name)
    
    def count(self, text: str, model: ModelName = "gpt-4") -> int:
        """
        Count tokens in text for specified model.
        
        Args:
            text: Text to count tokens for
            model: Target LLM model
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
        
        encoding = self._get_encoding(model)
        token_count = len(encoding.encode(text))
        
        # Apply Claude multiplier if needed
        if model.startswith("claude"):
            token_count = int(token_count * self.CLAUDE_MULTIPLIER)
        
        return token_count
    
    def count_node(self, node: "Node", model: ModelName = "gpt-4") -> int:
        """
        Count tokens for a code node.
        
        Includes signature, docstring, and content.
        """
        parts = []
        
        # File path as context
        parts.append(f"# {node.file_path}")
        
        # Signature
        if node.signature:
            parts.append(node.signature)
        
        # Docstring
        if node.docstring:
            parts.append(f'"""{node.docstring}"""')
        
        # Content
        parts.append(node.content)
        
        full_text = "\n".join(parts)
        return self.count(full_text, model)
    
    def count_batch(
        self, 
        texts: list[str], 
        model: ModelName = "gpt-4"
    ) -> list[int]:
        """Count tokens for multiple texts efficiently."""
        encoding = self._get_encoding(model)
        multiplier = self.CLAUDE_MULTIPLIER if model.startswith("claude") else 1.0
        
        return [
            int(len(encoding.encode(text)) * multiplier)
            for text in texts
        ]
    
    def estimate_from_chars(self, char_count: int, model: ModelName = "gpt-4") -> int:
        """
        Rough estimate of tokens from character count.
        
        Useful for quick estimates without full tokenization.
        Average: ~4 chars per token for code.
        """
        chars_per_token = 3.5 if model.startswith("claude") else 4.0
        return int(char_count / chars_per_token)
    
    def truncate_to_tokens(
        self, 
        text: str, 
        max_tokens: int, 
        model: ModelName = "gpt-4"
    ) -> str:
        """Truncate text to fit within token limit."""
        encoding = self._get_encoding(model)
        tokens = encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)
```

### Критерии приёмки
- [ ] Точный подсчёт для GPT-4, GPT-4o
- [ ] Приблизительный для Claude
- [ ] Batch counting эффективен
- [ ] Truncation работает корректно
- [ ] Кеширование encodings

---

### E5-2: Budget Allocator
**Оценка:** 4h | **Приоритет:** P0

### Описание
Алгоритмы оптимального распределения токенов между nodes.

### Реализация

```python
# src/codex_aura/budgeting/allocator.py

from dataclasses import dataclass
from enum import Enum
from typing import Callable

class AllocationStrategy(str, Enum):
    GREEDY = "greedy"           # Take highest-scored until budget exhausted
    PROPORTIONAL = "proportional"  # Allocate proportionally to scores
    KNAPSACK = "knapsack"       # Optimal 0/1 knapsack
    ADAPTIVE = "adaptive"       # Smart mix based on context

@dataclass
class AllocationResult:
    selected_nodes: list["RankedNode"]
    total_tokens: int
    budget_used_pct: float
    nodes_included: int
    nodes_truncated: int
    nodes_excluded: int
    strategy_used: AllocationStrategy

@dataclass
class RankedNode:
    node: "Node"
    score: float  # 0.0 - 1.0, higher = more relevant
    tokens: int   # pre-computed token count

class BudgetAllocator:
    """
    Allocate token budget across ranked nodes.
    
    Implements multiple strategies for different use cases:
    - GREEDY: Fast, good for most cases
    - PROPORTIONAL: Fair distribution
    - KNAPSACK: Optimal but slower
    - ADAPTIVE: Automatically chooses best strategy
    """
    
    def __init__(self, token_counter: TokenCounter):
        self.counter = token_counter
    
    def allocate(
        self,
        nodes: list[RankedNode],
        max_tokens: int,
        strategy: AllocationStrategy = AllocationStrategy.ADAPTIVE,
        model: str = "gpt-4",
        reserve_tokens: int = 500  # Reserve for prompt overhead
    ) -> AllocationResult:
        """
        Select nodes to include within token budget.
        
        Args:
            nodes: Ranked nodes with scores
            max_tokens: Maximum tokens allowed
            strategy: Allocation strategy to use
            model: Target LLM model
            reserve_tokens: Tokens to reserve for system prompt
            
        Returns:
            AllocationResult with selected nodes and stats
        """
        available_budget = max_tokens - reserve_tokens
        
        if not nodes:
            return AllocationResult(
                selected_nodes=[],
                total_tokens=0,
                budget_used_pct=0.0,
                nodes_included=0,
                nodes_truncated=0,
                nodes_excluded=0,
                strategy_used=strategy
            )
        
        # Pre-compute token counts if not already done
        for node in nodes:
            if node.tokens == 0:
                node.tokens = self.counter.count_node(node.node, model)
        
        # Select strategy
        if strategy == AllocationStrategy.ADAPTIVE:
            strategy = self._select_adaptive_strategy(nodes, available_budget)
        
        # Execute strategy
        if strategy == AllocationStrategy.GREEDY:
            selected = self._greedy_allocate(nodes, available_budget)
        elif strategy == AllocationStrategy.PROPORTIONAL:
            selected = self._proportional_allocate(nodes, available_budget)
        elif strategy == AllocationStrategy.KNAPSACK:
            selected = self._knapsack_allocate(nodes, available_budget)
        else:
            selected = self._greedy_allocate(nodes, available_budget)
        
        # Calculate stats
        total_tokens = sum(n.tokens for n in selected)
        
        return AllocationResult(
            selected_nodes=selected,
            total_tokens=total_tokens,
            budget_used_pct=round(total_tokens / available_budget * 100, 1),
            nodes_included=len(selected),
            nodes_truncated=0,  # TODO: track truncated
            nodes_excluded=len(nodes) - len(selected),
            strategy_used=strategy
        )
    
    def _greedy_allocate(
        self, 
        nodes: list[RankedNode], 
        budget: int
    ) -> list[RankedNode]:
        """
        Greedy allocation: take highest-scored nodes until budget exhausted.
        
        Time: O(n log n) for sorting
        """
        # Sort by score descending
        sorted_nodes = sorted(nodes, key=lambda n: n.score, reverse=True)
        
        selected = []
        used_tokens = 0
        
        for node in sorted_nodes:
            if used_tokens + node.tokens <= budget:
                selected.append(node)
                used_tokens += node.tokens
            elif used_tokens == 0 and node.tokens > budget:
                # First node too big - must include something
                # Truncate it to fit
                truncated = self._truncate_node(node, budget)
                selected.append(truncated)
                break
        
        return selected
    
    def _proportional_allocate(
        self, 
        nodes: list[RankedNode], 
        budget: int
    ) -> list[RankedNode]:
        """
        Proportional allocation: distribute budget based on scores.
        
        Each node gets budget proportional to its score.
        """
        total_score = sum(n.score for n in nodes)
        if total_score == 0:
            return self._greedy_allocate(nodes, budget)
        
        selected = []
        
        for node in nodes:
            # Calculate proportional budget for this node
            node_budget = int(budget * (node.score / total_score))
            
            if node.tokens <= node_budget:
                selected.append(node)
            elif node_budget > 100:  # Minimum useful size
                truncated = self._truncate_node(node, node_budget)
                selected.append(truncated)
        
        return selected
    
    def _knapsack_allocate(
        self, 
        nodes: list[RankedNode], 
        budget: int
    ) -> list[RankedNode]:
        """
        0/1 Knapsack optimal allocation.
        
        Maximizes total score within budget.
        Time: O(n * budget) - can be slow for large budgets.
        """
        n = len(nodes)
        
        # Scale down budget for DP if too large
        scale = 1
        if budget > 10000:
            scale = budget // 10000
            budget = budget // scale
            for node in nodes:
                node.tokens = node.tokens // scale
        
        # DP table
        dp = [[0.0] * (budget + 1) for _ in range(n + 1)]
        
        for i in range(1, n + 1):
            node = nodes[i - 1]
            for w in range(budget + 1):
                # Don't take this node
                dp[i][w] = dp[i - 1][w]
                
                # Take this node (if it fits)
                if node.tokens <= w:
                    take_value = dp[i - 1][w - node.tokens] + node.score
                    dp[i][w] = max(dp[i][w], take_value)
        
        # Backtrack to find selected nodes
        selected = []
        w = budget
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i - 1][w]:
                selected.append(nodes[i - 1])
                w -= nodes[i - 1].tokens
        
        # Restore scale
        if scale > 1:
            for node in nodes:
                node.tokens = node.tokens * scale
        
        return selected
    
    def _select_adaptive_strategy(
        self, 
        nodes: list[RankedNode], 
        budget: int
    ) -> AllocationStrategy:
        """Select best strategy based on input characteristics."""
        n = len(nodes)
        total_tokens = sum(n.tokens for n in nodes)
        
        # If total fits, greedy is fine
        if total_tokens <= budget:
            return AllocationStrategy.GREEDY
        
        # If many nodes and large budget, use greedy (knapsack too slow)
        if n > 100 or budget > 50000:
            return AllocationStrategy.GREEDY
        
        # If scores are uniform, proportional might be better
        scores = [n.score for n in nodes]
        score_variance = self._variance(scores)
        if score_variance < 0.1:
            return AllocationStrategy.PROPORTIONAL
        
        # Default to knapsack for optimal results
        return AllocationStrategy.KNAPSACK
    
    def _truncate_node(self, node: RankedNode, max_tokens: int) -> RankedNode:
        """Truncate node content to fit token budget."""
        truncated_content = self.counter.truncate_to_tokens(
            node.node.content,
            max_tokens - 50  # Reserve for metadata
        )
        
        truncated_node = node.node.copy()
        truncated_node.content = truncated_content + "\n# ... truncated ..."
        
        return RankedNode(
            node=truncated_node,
            score=node.score,
            tokens=max_tokens
        )
    
    @staticmethod
    def _variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
```

### Критерии приёмки
- [ ] Greedy strategy работает
- [ ] Proportional strategy работает  
- [ ] Knapsack strategy работает
- [ ] Adaptive автоматически выбирает лучший
- [ ] Никогда не превышает budget
- [ ] Truncation для слишком больших nodes

---

### E5-3: Content Summarization
**Оценка:** 3h | **Приоритет:** P1

### Описание
Интеллектуальное сжатие контента для экономии токенов.

### Реализация

```python
# src/codex_aura/budgeting/summarizer.py

from enum import Enum
from abc import ABC, abstractmethod

class SummarizationLevel(str, Enum):
    FULL = "full"           # Complete content
    SIGNATURE = "signature"  # Signature + docstring only
    STUB = "stub"           # Just signature
    REFERENCE = "reference"  # Just name and path

class ContentSummarizer:
    """
    Summarize code content to fit token budgets.
    
    Strategies (from most to least detail):
    1. FULL: Include everything
    2. SIGNATURE: Signature + docstring + type hints
    3. STUB: Just the signature
    4. REFERENCE: Just a reference to the node
    """
    
    def __init__(self, token_counter: TokenCounter, llm_client: "LLMClient" = None):
        self.counter = token_counter
        self.llm = llm_client
    
    def summarize_node(
        self,
        node: "Node",
        target_tokens: int,
        model: str = "gpt-4",
        level: SummarizationLevel = None
    ) -> str:
        """
        Summarize node to fit within target tokens.
        
        Automatically selects appropriate level if not specified.
        """
        full_content = self._format_full(node)
        full_tokens = self.counter.count(full_content, model)
        
        # If already fits, return full
        if full_tokens <= target_tokens:
            return full_content
        
        # Auto-select level if not specified
        if level is None:
            level = self._select_level(node, target_tokens, model)
        
        if level == SummarizationLevel.FULL:
            return self.counter.truncate_to_tokens(full_content, target_tokens, model)
        elif level == SummarizationLevel.SIGNATURE:
            return self._format_signature(node, target_tokens, model)
        elif level == SummarizationLevel.STUB:
            return self._format_stub(node)
        else:
            return self._format_reference(node)
    
    def _format_full(self, node: "Node") -> str:
        """Full content with file path context."""
        return f"# {node.file_path}:{node.start_line}\n{node.content}"
    
    def _format_signature(
        self, 
        node: "Node", 
        target_tokens: int,
        model: str
    ) -> str:
        """Signature + docstring format."""
        parts = [f"# {node.file_path}:{node.start_line}"]
        
        if node.type == "function":
            parts.append(node.signature or f"def {node.name}(...):")
            if node.docstring:
                # Include as much docstring as fits
                doc_tokens = target_tokens - self.counter.count("\n".join(parts), model) - 10
                if doc_tokens > 50:
                    truncated_doc = self.counter.truncate_to_tokens(
                        node.docstring, doc_tokens, model
                    )
                    parts.append(f'    """{truncated_doc}"""')
            parts.append("    ...")
        
        elif node.type == "class":
            parts.append(f"class {node.name}:")
            if node.docstring:
                doc_tokens = target_tokens - self.counter.count("\n".join(parts), model) - 10
                if doc_tokens > 50:
                    truncated_doc = self.counter.truncate_to_tokens(
                        node.docstring, doc_tokens, model
                    )
                    parts.append(f'    """{truncated_doc}"""')
            
            # Include method signatures
            for method in node.methods[:5]:  # Top 5 methods
                parts.append(f"    {method.signature}")
            if len(node.methods) > 5:
                parts.append(f"    # ... and {len(node.methods) - 5} more methods")
        
        return "\n".join(parts)
    
    def _format_stub(self, node: "Node") -> str:
        """Minimal stub format."""
        return f"# {node.file_path}:{node.start_line}\n{node.signature or node.name}"
    
    def _format_reference(self, node: "Node") -> str:
        """Just a reference."""
        return f"# See: {node.fqn} in {node.file_path}"
    
    def _select_level(
        self, 
        node: "Node", 
        target_tokens: int,
        model: str
    ) -> SummarizationLevel:
        """Auto-select appropriate summarization level."""
        # Try each level from most to least detailed
        levels = [
            SummarizationLevel.SIGNATURE,
            SummarizationLevel.STUB,
            SummarizationLevel.REFERENCE
        ]
        
        for level in levels:
            content = self.summarize_node(node, target_tokens * 2, model, level)
            if self.counter.count(content, model) <= target_tokens:
                return level
        
        return SummarizationLevel.REFERENCE
    
    async def llm_summarize(
        self,
        node: "Node",
        target_tokens: int,
        model: str = "gpt-4"
    ) -> str:
        """
        Use LLM to intelligently summarize code.
        
        More expensive but produces better summaries.
        """
        if not self.llm:
            return self.summarize_node(node, target_tokens, model, SummarizationLevel.SIGNATURE)
        
        prompt = f"""Summarize this code in approximately {target_tokens} tokens.
Keep the most important functionality, type signatures, and key logic.

```{node.language}
{node.content}
```

Provide a concise summary that preserves the essential information."""

        response = await self.llm.generate(
            prompt,
            max_tokens=target_tokens + 50,
            model="gpt-3.5-turbo"  # Use cheaper model for summarization
        )
        
        return f"# {node.file_path} (summarized)\n{response}"
```

### Критерии приёмки
- [ ] 4 уровня summarization работают
- [ ] Auto-selection выбирает правильный уровень
- [ ] LLM summarization опционален
- [ ] Сохраняет type signatures
- [ ] Включает номера строк

---

### E5-4: Budget Presets
**Оценка:** 1h | **Приоритет:** P1

### Реализация

```python
# src/codex_aura/budgeting/presets.py

from dataclasses import dataclass

@dataclass
class ModelBudgetPreset:
    model: str
    context_window: int       # Total context window
    recommended_context: int  # Recommended for context (留 room for response)
    max_context: int          # Maximum safe context
    chars_per_token: float    # For quick estimates

BUDGET_PRESETS: dict[str, ModelBudgetPreset] = {
    "gpt-4": ModelBudgetPreset(
        model="gpt-4",
        context_window=8192,
        recommended_context=4000,
        max_context=6000,
        chars_per_token=4.0
    ),
    "gpt-4-turbo": ModelBudgetPreset(
        model="gpt-4-turbo",
        context_window=128000,
        recommended_context=16000,
        max_context=64000,
        chars_per_token=4.0
    ),
    "gpt-4o": ModelBudgetPreset(
        model="gpt-4o",
        context_window=128000,
        recommended_context=16000,
        max_context=64000,
        chars_per_token=4.0
    ),
    "gpt-3.5-turbo": ModelBudgetPreset(
        model="gpt-3.5-turbo",
        context_window=16385,
        recommended_context=8000,
        max_context=12000,
        chars_per_token=4.0
    ),
    "claude-3-opus": ModelBudgetPreset(
        model="claude-3-opus",
        context_window=200000,
        recommended_context=32000,
        max_context=100000,
        chars_per_token=3.5
    ),
    "claude-3.5-sonnet": ModelBudgetPreset(
        model="claude-3.5-sonnet",
        context_window=200000,
        recommended_context=32000,
        max_context=100000,
        chars_per_token=3.5
    ),
    "claude-3-haiku": ModelBudgetPreset(
        model="claude-3-haiku",
        context_window=200000,
        recommended_context=16000,
        max_context=50000,
        chars_per_token=3.5
    ),
}

def get_preset(model: str) -> ModelBudgetPreset:
    """Get budget preset for model, with fallback."""
    # Exact match
    if model in BUDGET_PRESETS:
        return BUDGET_PRESETS[model]
    
    # Partial match
    for key, preset in BUDGET_PRESETS.items():
        if key in model or model in key:
            return preset
    
    # Default fallback
    return BUDGET_PRESETS["gpt-4"]

# API endpoint
@router.get("/api/v1/budgets/presets")
async def list_presets() -> dict[str, ModelBudgetPreset]:
    return BUDGET_PRESETS

@router.get("/api/v1/budgets/presets/{model}")
async def get_model_preset(model: str) -> ModelBudgetPreset:
    return get_preset(model)
```

---

### E5-5: Budget Analytics
**Оценка:** 2h | **Приоритет:** P2

### Реализация

```python
# src/codex_aura/budgeting/analytics.py

@dataclass
class BudgetAnalytics:
    period: str  # "day", "week", "month"
    total_requests: int
    avg_budget_used_pct: float
    avg_nodes_included: int
    avg_nodes_excluded: int
    total_tokens_saved: int  # vs naive approach
    tokens_saved_pct: float
    strategy_distribution: dict[str, int]  # strategy -> count

class BudgetAnalyticsService:
    """Track and analyze token budget usage."""
    
    async def record_allocation(
        self,
        repo_id: str,
        user_id: str,
        result: AllocationResult
    ):
        """Record allocation for analytics."""
        await self.db.insert_budget_event(
            repo_id=repo_id,
            user_id=user_id,
            budget_requested=result.total_tokens,
            budget_used=result.total_tokens,
            nodes_included=result.nodes_included,
            nodes_excluded=result.nodes_excluded,
            strategy=result.strategy_used.value,
            timestamp=datetime.utcnow()
        )
    
    async def get_analytics(
        self,
        user_id: str,
        period: str = "week"
    ) -> BudgetAnalytics:
        """Get budget analytics for user."""
        since = self._get_period_start(period)
        events = await self.db.get_budget_events(user_id, since=since)
        
        if not events:
            return BudgetAnalytics(period=period, ...)
        
        # Calculate naive tokens (what it would be without budgeting)
        # Assume 3x more tokens without smart selection
        naive_tokens = sum(e.budget_used * 3 for e in events)
        actual_tokens = sum(e.budget_used for e in events)
        tokens_saved = naive_tokens - actual_tokens
        
        return BudgetAnalytics(
            period=period,
            total_requests=len(events),
            avg_budget_used_pct=sum(e.budget_used_pct for e in events) / len(events),
            avg_nodes_included=sum(e.nodes_included for e in events) / len(events),
            avg_nodes_excluded=sum(e.nodes_excluded for e in events) / len(events),
            total_tokens_saved=tokens_saved,
            tokens_saved_pct=round(tokens_saved / naive_tokens * 100, 1),
            strategy_distribution=Counter(e.strategy for e in events)
        )
```

---

### E5-6: Budget API Endpoint
**Оценка:** 2h | **Приоритет:** P0

### Реализация

```python
# src/codex_aura/api/budget.py

@router.post("/api/v1/budget/allocate")
async def allocate_budget(
    request: BudgetAllocationRequest,
    allocator: BudgetAllocator = Depends(get_allocator),
    analytics: BudgetAnalyticsService = Depends(get_analytics),
    current_user: User = Depends(get_current_user)
) -> AllocationResult:
    """
    Allocate token budget across nodes.
    
    This is typically called internally by /context endpoint,
    but can be used directly for custom allocation.
    """
    # Get preset if model specified
    if request.model:
        preset = get_preset(request.model)
        if request.max_tokens is None:
            request.max_tokens = preset.recommended_context
    
    result = allocator.allocate(
        nodes=request.nodes,
        max_tokens=request.max_tokens,
        strategy=request.strategy,
        model=request.model
    )
    
    # Record analytics
    await analytics.record_allocation(
        repo_id=request.repo_id,
        user_id=current_user.id,
        result=result
    )
    
    return result
```

---

## E6: 🎯 Smart Context API (Детальная реализация)

### E6-1: Context Request Model
**Оценка:** 1h | **Приоритет:** P0

```python
# src/codex_aura/api/models/context.py

from pydantic import BaseModel, Field
from typing import Literal

class ContextRequest(BaseModel):
    """Request for intelligent code context."""
    
    repo_id: str = Field(..., description="Repository identifier")
    task: str = Field(..., description="Task description for semantic relevance")
    
    # Entry points
    entry_points: list[str] = Field(
        default=[],
        description="Starting points for graph traversal (file paths, FQNs, or globs)"
    )
    
    # Graph traversal
    depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum depth for dependency traversal"
    )
    
    # Token budget
    max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens for context (uses preset if not specified)"
    )
    model: str = Field(
        default="gpt-4",
        description="Target LLM model for token counting"
    )
    budget_strategy: AllocationStrategy = Field(
        default=AllocationStrategy.ADAPTIVE,
        description="Token allocation strategy"
    )
    
    # Filters
    include_tests: bool = Field(default=False, description="Include test files")
    include_docs: bool = Field(default=True, description="Include docstrings")
    file_patterns: list[str] = Field(
        default=[],
        description="Glob patterns to filter files (e.g., ['*.py', '!*_test.py'])"
    )
    
    # Output format
    format: Literal["plain", "markdown", "xml", "json"] = Field(
        default="markdown",
        description="Output format for context"
    )
    include_metadata: bool = Field(
        default=True,
        description="Include file paths, line numbers in output"
    )

class ContextResponse(BaseModel):
    """Response with code context."""
    
    context: str = Field(..., description="Formatted code context")
    
    nodes: list[NodeSummary] = Field(
        ...,
        description="Summary of included nodes"
    )
    
    stats: ContextStats = Field(..., description="Context statistics")
    
    # For debugging/transparency
    search_scores: dict[str, float] | None = Field(
        default=None,
        description="Semantic search scores for each node (if requested)"
    )

class ContextStats(BaseModel):
    total_tokens: int
    budget_used_pct: float
    nodes_included: int
    nodes_excluded: int
    nodes_truncated: int
    search_mode: str  # "graph", "semantic", "hybrid"
    allocation_strategy: str
    generation_time_ms: int
```

---

### E6-2: Context Builder Pipeline
**Оценка:** 4h | **Приоритет:** P0

```python
# src/codex_aura/context/builder.py

class ContextBuilder:
    """
    Build intelligent code context for AI agents.
    
    Pipeline:
    1. Resolve entry points
    2. Graph traversal (structural relevance)
    3. Semantic search (content relevance)
    4. Hybrid ranking
    5. Budget allocation
    6. Format output
    """
    
    def __init__(
        self,
        graph_storage: GraphStorage,
        semantic_search: SemanticSearch,
        budget_allocator: BudgetAllocator,
        token_counter: TokenCounter,
        summarizer: ContentSummarizer
    ):
        self.graph = graph_storage
        self.search = semantic_search
        self.allocator = budget_allocator
        self.counter = token_counter
        self.summarizer = summarizer
    
    async def build(self, request: ContextRequest) -> ContextResponse:
        """Build context for the given request."""
        start_time = time.time()
        
        # Step 1: Resolve entry points
        entry_nodes = await self._resolve_entry_points(
            request.repo_id,
            request.entry_points
        )
        
        # Step 2: Get structurally relevant nodes (graph traversal)
        graph_nodes = await self._traverse_graph(
            request.repo_id,
            entry_nodes,
            depth=request.depth
        )
        
        # Step 3: Get semantically relevant nodes
        semantic_nodes = await self._semantic_search(
            request.repo_id,
            request.task,
            limit=100
        )
        
        # Step 4: Combine and rank
        ranked_nodes = self._hybrid_rank(
            graph_nodes,
            semantic_nodes,
            task=request.task
        )
        
        # Step 5: Apply filters
        filtered_nodes = self._apply_filters(
            ranked_nodes,
            include_tests=request.include_tests,
            file_patterns=request.file_patterns
        )
        
        # Step 6: Allocate budget
        max_tokens = request.max_tokens or get_preset(request.model).recommended_context
        
        allocation = self.allocator.allocate(
            nodes=filtered_nodes,
            max_tokens=max_tokens,
            strategy=request.budget_strategy,
            model=request.model
        )
        
        # Step 7: Format output
        formatted_context = await self._format_context(
            allocation.selected_nodes,
            format=request.format,
            include_metadata=request.include_metadata,
            include_docs=request.include_docs
        )
        
        generation_time = int((time.time() - start_time) * 1000)
        
        return ContextResponse(
            context=formatted_context,
            nodes=[NodeSummary.from_node(n.node) for n in allocation.selected_nodes],
            stats=ContextStats(
                total_tokens=allocation.total_tokens,
                budget_used_pct=allocation.budget_used_pct,
                nodes_included=allocation.nodes_included,
                nodes_excluded=allocation.nodes_excluded,
                nodes_truncated=allocation.nodes_truncated,
                search_mode="hybrid",
                allocation_strategy=allocation.strategy_used.value,
                generation_time_ms=generation_time
            )
        )
    
    async def _resolve_entry_points(
        self,
        repo_id: str,
        entry_points: list[str]
    ) -> list[str]:
        """Resolve entry points to node FQNs."""
        resolved = []
        
        for entry in entry_points:
            # Glob pattern
            if "*" in entry:
                matches = await self.graph.find_nodes_by_glob(repo_id, entry)
                resolved.extend(matches)
            
            # File path
            elif entry.endswith(".py"):
                nodes = await self.graph.get_nodes_in_file(repo_id, entry)
                resolved.extend(n.fqn for n in nodes)
            
            # Line reference (file.py:42)
            elif ":" in entry and entry.split(":")[1].isdigit():
                file_path, line = entry.rsplit(":", 1)
                node = await self.graph.get_node_at_line(repo_id, file_path, int(line))
                if node:
                    resolved.append(node.fqn)
            
            # FQN
            else:
                resolved.append(entry)
        
        return resolved
    
    async def _traverse_graph(
        self,
        repo_id: str,
        entry_fqns: list[str],
        depth: int
    ) -> list[RankedNode]:
        """Traverse graph from entry points."""
        all_nodes = {}
        
        for fqn in entry_fqns:
            # Get dependencies and dependents
            deps = await self.graph.get_dependencies(repo_id, fqn, depth)
            dependents = await self.graph.get_dependents(repo_id, fqn, depth)
            
            for node, distance in deps + dependents:
                if node.fqn not in all_nodes:
                    # Score based on distance (closer = higher)
                    score = 1.0 / (distance + 1)
                    all_nodes[node.fqn] = RankedNode(
                        node=node,
                        score=score,
                        tokens=0  # Will be computed later
                    )
                else:
                    # Update score if this path is shorter
                    new_score = 1.0 / (distance + 1)
                    if new_score > all_nodes[node.fqn].score:
                        all_nodes[node.fqn].score = new_score
        
        return list(all_nodes.values())
    
    async def _semantic_search(
        self,
        repo_id: str,
        task: str,
        limit: int
    ) -> list[RankedNode]:
        """Get semantically relevant nodes."""
        results = await self.search.search(repo_id, task, limit=limit)
        
        return [
            RankedNode(
                node=r.node,
                score=r.score,  # Cosine similarity
                tokens=0
            )
            for r in results
        ]
    
    def _hybrid_rank(
        self,
        graph_nodes: list[RankedNode],
        semantic_nodes: list[RankedNode],
        task: str,
        graph_weight: float = 0.4,
        semantic_weight: float = 0.6
    ) -> list[RankedNode]:
        """Combine graph and semantic scores."""
        scores = {}
        nodes = {}
        
        # Add graph scores
        for rn in graph_nodes:
            scores[rn.node.fqn] = {"graph": rn.score, "semantic": 0.0}
            nodes[rn.node.fqn] = rn.node
        
        # Add semantic scores
        for rn in semantic_nodes:
            if rn.node.fqn in scores:
                scores[rn.node.fqn]["semantic"] = rn.score
            else:
                scores[rn.node.fqn] = {"graph": 0.1, "semantic": rn.score}
                nodes[rn.node.fqn] = rn.node
        
        # Combine scores
        ranked = []
        for fqn, s in scores.items():
            combined = graph_weight * s["graph"] + semantic_weight * s["semantic"]
            ranked.append(RankedNode(
                node=nodes[fqn],
                score=combined,
                tokens=0
            ))
        
        return sorted(ranked, key=lambda r: r.score, reverse=True)
    
    def _apply_filters(
        self,
        nodes: list[RankedNode],
        include_tests: bool,
        file_patterns: list[str]
    ) -> list[RankedNode]:
        """Apply filters to nodes."""
        filtered = []
        
        for rn in nodes:
            # Test filter
            if not include_tests and self._is_test_file(rn.node.file_path):
                continue
            
            # Pattern filter
            if file_patterns and not self._matches_patterns(rn.node.file_path, file_patterns):
                continue
            
            filtered.append(rn)
        
        return filtered
    
    async def _format_context(
        self,
        nodes: list[RankedNode],
        format: str,
        include_metadata: bool,
        include_docs: bool
    ) -> str:
        """Format nodes into context string."""
        formatter = ContextFormatter(
            include_metadata=include_metadata,
            include_docs=include_docs
        )
        
        if format == "markdown":
            return formatter.to_markdown(nodes)
        elif format == "xml":
            return formatter.to_xml(nodes)
        elif format == "json":
            return formatter.to_json(nodes)
        else:
            return formatter.to_plain(nodes)
```

---

### E6-3: Context Formatters
**Оценка:** 3h | **Приоритет:** P0

```python
# src/codex_aura/context/formatters.py

class ContextFormatter:
    """Format code nodes into different output formats."""
    
    def __init__(self, include_metadata: bool = True, include_docs: bool = True):
        self.include_metadata = include_metadata
        self.include_docs = include_docs
    
    def to_markdown(self, nodes: list[RankedNode]) -> str:
        """Format as Markdown with code blocks."""
        output = ["## Relevant Code Context\n"]
        
        # Group by file
        by_file = defaultdict(list)
        for rn in nodes:
            by_file[rn.node.file_path].append(rn)
        
        for file_path, file_nodes in by_file.items():
            output.append(f"### {file_path}\n")
            
            for rn in sorted(file_nodes, key=lambda x: x.node.start_line):
                node = rn.node
                
                if self.include_metadata:
                    output.append(f"**{node.type.title()}: {node.name}** (lines {node.start_line}-{node.end_line})\n")
                
                lang = self._detect_language(file_path)
                output.append(f"```{lang}")
                output.append(node.content)
                output.append("```\n")
        
        return "\n".join(output)
    
    def to_xml(self, nodes: list[RankedNode]) -> str:
        """Format as XML (useful for Claude prompts)."""
        output = ["<code_context>"]
        
        for rn in nodes:
            node = rn.node
            output.append(f'  <file path="{node.file_path}">')
            output.append(f'    <{node.type} name="{node.name}" lines="{node.start_line}-{node.end_line}">')
            output.append(f"      <![CDATA[{node.content}]]>")
            output.append(f"    </{node.type}>")
            output.append("  </file>")
        
        output.append("</code_context>")
        return "\n".join(output)
    
    def to_json(self, nodes: list[RankedNode]) -> str:
        """Format as JSON."""
        data = {
            "context": [
                {
                    "file_path": rn.node.file_path,
                    "type": rn.node.type,
                    "name": rn.node.name,
                    "start_line": rn.node.start_line,
                    "end_line": rn.node.end_line,
                    "content": rn.node.content,
                    "relevance_score": rn.score
                }
                for rn in nodes
            ]
        }
        return json.dumps(data, indent=2)
    
    def to_plain(self, nodes: list[RankedNode]) -> str:
        """Plain text format."""
        output = []
        
        for rn in nodes:
            node = rn.node
            output.append(f"# {node.file_path}:{node.start_line}")
            output.append(node.content)
            output.append("")  # Empty line between nodes
        
        return "\n".join(output)
```

---

### E6-4: Entry Point Resolution
**Оценка:** 2h | **Приоритет:** P0

*Уже включено в E6-2*

---

### E6-5: Context Caching
**Оценка:** 2h | **Приоритет:** P1

```python
# src/codex_aura/context/cache.py

import hashlib
from redis import Redis

class ContextCache:
    """Cache context responses for repeated requests."""
    
    def __init__(self, redis: Redis, ttl: int = 300):
        self.redis = redis
        self.ttl = ttl
    
    def _cache_key(self, request: ContextRequest, graph_version: str) -> str:
        """Generate cache key from request."""
        # Include graph version to invalidate on updates
        key_data = {
            "repo_id": request.repo_id,
            "task": request.task,
            "entry_points": sorted(request.entry_points),
            "depth": request.depth,
            "max_tokens": request.max_tokens,
            "model": request.model,
            "graph_version": graph_version
        }
        key_hash = hashlib.sha256(json.dumps(key_data).encode()).hexdigest()[:16]
        return f"ctx:{request.repo_id}:{key_hash}"
    
    async def get(
        self,
        request: ContextRequest,
        graph_version: str
    ) -> ContextResponse | None:
        """Get cached context if available."""
        key = self._cache_key(request, graph_version)
        cached = await self.redis.get(key)
        
        if cached:
            return ContextResponse.parse_raw(cached)
        return None
    
    async def set(
        self,
        request: ContextRequest,
        graph_version: str,
        response: ContextResponse
    ):
        """Cache context response."""
        key = self._cache_key(request, graph_version)
        await self.redis.setex(key, self.ttl, response.json())
    
    async def invalidate_repo(self, repo_id: str):
        """Invalidate all cached contexts for a repo."""
        pattern = f"ctx:{repo_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```

---

### E6-6: Rate Limiting
**Оценка:** 2h | **Приоритет:** P0

```python
# src/codex_aura/api/middleware/rate_limit.py

from slowapi import Limiter
from slowapi.util import get_remote_address

# Different limits by plan
RATE_LIMITS = {
    "free": "100/day",
    "pro": "10000/day",
    "team": "50000/day",
    "enterprise": "unlimited"
}

limiter = Limiter(key_func=get_remote_address)

def get_rate_limit(user: User) -> str:
    """Get rate limit string for user's plan."""
    return RATE_LIMITS.get(user.plan, RATE_LIMITS["free"])

@router.post("/api/v1/context")
@limiter.limit(lambda: get_rate_limit(get_current_user()))
async def get_context(
    request: ContextRequest,
    builder: ContextBuilder = Depends(get_builder),
    cache: ContextCache = Depends(get_cache),
    current_user: User = Depends(get_current_user)
) -> ContextResponse:
    """Get intelligent code context for AI agents."""
    
    # Check cache
    graph_version = await get_graph_version(request.repo_id)
    cached = await cache.get(request, graph_version)
    if cached:
        return cached
    
    # Build context
    response = await builder.build(request)
    
    # Cache result
    await cache.set(request, graph_version, response)
    
    return response
```

---

### E6-7: Context Endpoint (Final)
**Оценка:** 2h | **Приоритет:** P0

*Уже включено в E6-6*

### Критерии приёмки E6
- [ ] POST /context возвращает релевантный контекст
- [ ] Hybrid search (graph + semantic) работает
- [ ] 4 формата вывода (markdown, xml, json, plain)
- [ ] Кеширование работает
- [ ] Rate limiting по плану
- [ ] Метрики генерации (время, токены)