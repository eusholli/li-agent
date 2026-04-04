# System Patterns - LinkedIn Article Generator

## Architecture Overview

### Enhanced Core System Design with Runtime Model Selection and Parallel Generation
```
Input (Outline/Draft) 
    ↓
Model Selection & Configuration (component-specific LLM models)
    ↓
Dynamic Criteria Extraction (from li_article_judge.py)
    ↓
Parallel Version Generation (DSPy Parallel with temperature variation)
    ↓
Combined Quality + Length Scoring (li_article_judge.py with configurable model)
    ↓
Interactive Version Comparison (success metrics and performance tracking)
    ↓
Smart Version Selection (manual, best-score, or auto-selection)
    ↓
Export System (directory-based with automatic conflict resolution)
    ↓
Target Achievement (≥89% score + 2000-2500 words achieved simultaneously)
```

### Parallel Generation Architecture Pattern
```python
# Parallel Generator Creation with Temperature Variation
def create_parallel_generators(args, base_models, num_versions):
    generators = []
    temperatures = [0.1, 0.5, 0.9]  # Focused, Standard, Creative
    if num_versions > 3:
        temperatures.extend([0.3, 0.7][:num_versions - 3])

    for temp in temperatures[:num_versions]:
        # Create model config with different temperature for generator only
        version_models = base_models.copy()
        generator_model = get_openrouter_model(args.generator_model, temp=temp)
        version_models["generator"] = generator_model
        # Create generator instance with temperature-specific model
        generator = LinkedInArticleGenerator(models=version_models, ...)
        generators.append(generator)
    return generators

# DSPy Parallel Execution Pattern
def run_parallel_generation(generators, draft_text):
    parallel = dspy.Parallel(num_threads=len(generators))
    parallel_calls = []

    for i, generator in enumerate(generators):
        def make_generate_call(gen, draft, version_num=i + 1):
            def generate_call():
                try:
                    result = gen.generate_article(draft, verbose=False)
                    return {
                        "version": version_num,
                        "success": True,
                        "result": result,
                        "generation_time": time.time() - start_time,
                        "temperature": getattr(gen.models["generator"], "temperature", 0.5),
                    }
                except Exception as e:
                    return {"version": version_num, "success": False, "error": str(e)}
            return generate_call

        parallel_calls.append((make_generate_call(generator, draft_text), {}))

    # Execute in parallel using DSPy's Parallel module
    parallel_results = parallel(parallel_calls)
    return parallel_results
```

### Thread-Safe Cache Pattern
```python
# Module-level cache with thread-safety
_cache: Dict[str, Any] = {"searches": {}, "extractions": {}}
_cache_lock = asyncio.Lock()
_cache_initialized = False

async def get_cached_search(query: str) -> Optional[dict]:
    """Async wrapper for cache read."""
    async with _cache_lock:
        search_data = _cache["searches"].get(query)
        return search_data.get("response") if search_data else None

async def set_cached_search(query: str, response: dict, cache_file: str) -> None:
    """Async wrapper for cache write."""
    async with _cache_lock:
        _cache["searches"][query] = {"timestamp": time.time(), "response": response}
        # Run sync save in thread pool to avoid blocking event loop
        await asyncio.to_thread(save_cache, cache_file)

def save_cache(cache_file: str) -> None:
    """Synchronously save cache to file atomically."""
    try:
        # Write to temp file first
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(cache_file))
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(_cache, f, indent=2, ensure_ascii=False)
            # Atomic rename
            os.rename(temp_path, cache_file)
        except Exception:
            os.unlink(temp_path)
            raise
    except Exception as e:
        logging.warning(f"Failed to save cache: {e}")
```

### Export System Pattern
```python
class LinkedInArticleGenerator:
    def _resolve_directory_name(self, base_name: str) -> str:
        """Resolve directory name with automatic numbering if conflicts exist."""
        if not os.path.exists(base_name):
            os.makedirs(base_name, exist_ok=False)
            return base_name

        counter = 1
        while True:
            candidate = f"{base_name}-{counter}"
            if not os.path.exists(candidate):
                os.makedirs(candidate, exist_ok=False)
                return candidate
            counter += 1

    def _export_single_version(self, version: ArticleVersion, directory_name: str):
        """Export a single article version with metadata."""
        filename = f"version-{version.version}.md"
        filepath = os.path.join(directory_name, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                # Add version metadata header
                f.write(f"# Article Version {version.version}\n\n")
                f.write(f"**Generated:** {version.timestamp}\n")
                if version.judgement:
                    f.write(f"**Score:** {version.judgement.percentage:.1f}%\n")
                    f.write(f"**Word Count:** {version.judgement.word_count}\n")
                    f.write(f"**Performance Tier:** {version.judgement.performance_tier}\n")
                f.write("\n---\n\n")
                # Write article content
                f.write(version.content)
        except Exception as e:
            print(f"❌ Failed to export version {version.version}: {e}")
```

### Component Relationships

### Core Modules
1. **Enhanced DSPy Factory:** Model instance management and caching
2. **CriteriaExtractor:** Dynamically loads and parses scoring criteria
3. **ArticleGenerator:** Creates and improves articles using configurable DSPy models
4. **ArticleScorer:** Evaluates articles using configurable scoring models
5. **Fast RAG Retriever:** High-performance async web search and intelligent content packing
6. **Topic Extraction System:** DSPy-based analysis for optimal search query generation
7. **WordCountManager:** Manages length constraints and adjustments
8. **FeedbackProcessor:** Converts scores into improvement instructions
9. **IterationController:** Orchestrates the improvement loop with optimal models
10. **ExportManager:** Handles version export with directory management
11. **FactChecker (fc_oc_v2.py):** One-call fact-checking with auto-correction

### Data Flow Patterns
```
COMMAND-LINE ARGUMENTS
    ↓ (model selection + export config)
Enhanced Factory Pattern
    ↓ (model instances)
SCORING_CRITERIA (li_article_judge.py)
    ↓ (import & parse)
CriteriaExtractor
    ↓ (criteria summary)
Parallel Generation System
    ↓ (multiple versions with temperature variation)
Fast RAG System (rag_fast.py)
    ↓ (topic extraction → async search → intelligent packing)
ArticleGenerator (with generator_model + RAG context)
    ↓ (generated articles)
WordCountManager
    ↓ (word count validation)
LinkedInArticleScorer (with judge_model)
    ↓ (score results)
Version Comparison
    ↓ (interactive selection)
ExportManager
    ↓ (directory-based export)
Final Result
```

## Quality Assurance Patterns

### Validation Pipeline Pattern
1. **Input Validation:** Ensure outline/draft meets minimum requirements
2. **Generation Validation:** Verify article structure and completeness
3. **Word Count Validation:** Check length constraints
4. **Quality Validation:** Score against criteria
5. **Export Validation:** Ensure proper file and directory creation

### Error Handling Pattern
```python
try:
    result = generate_article(outline)
except GenerationError:
    # Fallback to simpler generation approach
    result = fallback_generation(outline)
except ScoringError:
    # Use cached scoring or manual review
    result = handle_scoring_failure(article)
except ExportError:
    # Handle directory creation or file write failures
    result = handle_export_failure(version)
```

## Performance Optimization Patterns

### Thread-Safe Cache Strategy
- **Module-Level Cache:** Single shared instance across components
- **Async Lock Protection:** Prevent concurrent access corruption
- **Atomic File Operations:** Temp file + rename for data integrity
- **Thread Pool Isolation:** File I/O in separate threads
- **Lazy Initialization:** Cache loads once when first needed

### Parallel Generation Strategy
- **Temperature Variation:** Different settings for diverse outputs
- **Controlled Concurrency:** Configurable worker count
- **Resource Management:** Efficient model instance reuse
- **Version Tracking:** Complete metadata for each variant
- **Interactive Selection:** User control over final version

### Export System Strategy
- **Directory Management:** Automatic conflict resolution
- **Atomic Operations:** Safe file creation and updates
- **Metadata Tracking:** Complete version information
- **Format Flexibility:** Markdown with front matter
- **Summary Generation:** Comparative analysis in summary.md

## Monitoring and Debugging Patterns

### Enhanced Progress Tracking Pattern
```python
class ProgressTracker:
    def track_iteration(self, iteration, score, word_count, improvements, models_used):
        # Log progress metrics
        # Track model performance per operation
        # Identify improvement trends
        # Monitor parallel generation metrics
        # Track export operations
```

### Enhanced Debug Information Pattern
- **Iteration Logging:** Track changes between versions
- **Model Usage Tracking:** Log which models used for each operation
- **Score Breakdown:** Detailed category-by-category analysis
- **Export Tracking:** Monitor file and directory operations
- **Cache Statistics:** Track hit rates and storage efficiency

## Scalability Patterns

### Enhanced Batch Processing Pattern
- **Multiple Articles:** Process multiple outlines in parallel
- **Shared Resources:** Reuse cached models and data
- **Export Organization:** Structured directory hierarchy
- **Resource Management:** Controlled concurrency limits
- **Result Aggregation:** Combined analysis and reporting

### Advanced Configuration Management Pattern
- **Environment-Specific Settings:** Different targets for different use cases
- **User Preferences:** Customizable quality and length preferences
- **Model Configuration Profiles:** Predefined model combinations
- **Export Settings:** Directory and format preferences
- **Performance Profiling:** Track model effectiveness
