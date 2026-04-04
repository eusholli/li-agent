# Technical Context - LinkedIn Article Generator

## Technology Stack

### Core Framework
- **DSPy:** Stanford's framework for programming language models
  - Version: Latest (from stanfordnlp/dspy)
  - Purpose: Structured LLM interactions and optimization
  - Key Features: Signatures, Modules, ChainOfThought, Parallel execution

### Dependencies
- **Python 3.8+:** Core runtime environment
- **dspy:** Main framework for LLM programming
- **pydantic:** Data validation and type safety
- **python-dotenv:** Environment variable management
- **tavily-python:** High-performance web search API client for RAG
- **tiktoken:** Accurate token counting for context window management
- **asyncio:** Built-in async support for concurrent operations
- **attachments:** File processing and text extraction
- **tempfile:** Atomic file operations for cache management

### LLM Provider Integration
- **OpenRouter API:** Primary LLM access point
- **Default Model:** openrouter/moonshotai/kimi-k2:free (fallback for all components)
- **Component-Specific Models:** Runtime selection via command-line arguments
- **Enhanced Configuration:** Via extended dspy_factory.py with model instance management
- **Model Caching:** Performance optimization through instance reuse
- **API Key:** Stored in .env file as OPENROUTER_API_KEY

## Existing Infrastructure

### Enhanced Factory System (dspy_factory.py)
- **Model Instance Management:** New functions for component-specific model creation
  - `get_model_instance(model_name)`: Creates and caches LM instances
  - `create_component_lm(model_name)`: Wraps models in ConfiguredLM for context management
  - `get_fallback_model()`: Provides intelligent fallback to default model
- **Performance Caching:** `_model_instance_cache` dictionary prevents redundant initialization
- **Backward Compatibility:** Existing `setup_dspy_provider()` unchanged for legacy usage
- **Error Handling:** Graceful fallbacks when model creation fails
- **Temperature Support:** Model creation with configurable temperature for parallel generation

### Thread-Safe Cache System (rag_fast.py)
- **Module-Level Cache:** Shared instance across all components
- **Async Lock Protection:** asyncio.Lock for thread safety
- **Atomic File Operations:** Temp file + rename pattern
- **Thread Pool:** File I/O in separate threads
- **Lazy Loading:** Cache initialized on first use
- **Error Recovery:** Robust handling of file operations
- **Cache Structure:** Separate search and extraction caches
- **Persistence:** JSON-based file storage with atomic updates

### Export System (linkedin_article_generator.py)
- **Directory Management:** Automatic conflict resolution
- **Version Organization:** Individual files per version
- **Metadata Storage:** Complete version information
- **Summary Generation:** Comparative analysis in summary.md
- **Format:** Markdown with front matter
- **Error Handling:** Robust recovery from file operations
- **Auto Mode:** Automatic export on target achievement
- **Command Line:** --export-dir argument with conflict handling

### Scoring System (li_article_judge.py)
- **Architecture:** Comprehensive 180-point evaluation system
- **Categories:** 8 major scoring categories with weighted criteria
- **Data Models:** Pydantic-based ScoreResultModel and ArticleScoreModel
- **Integration:** Direct Python import for dynamic criteria access
- **Model Selection:** Optional model_name parameter for component-specific scoring
- **Word Count Integration:** ArticleScoreModel enhanced with optional word_count field

### Parallel Generation System
- **DSPy Parallel:** Built-in concurrent execution
- **Temperature Variation:** [0.1, 0.5, 0.9] for diversity
- **Worker Management:** Configurable async_max_workers
- **Resource Control:** Shared model instances
- **Version Tracking:** Complete metadata per variant
- **Interactive Selection:** Manual or automatic choice

## Development Constraints

### Runtime Model Selection Requirements
- **Component Independence:** Each component can use different models
- **Backward Compatibility:** Existing --model argument must continue working
- **Fallback Logic:** Graceful degradation when specific models unavailable
- **Cost Optimization:** Support for mixing free and paid models
- **Performance:** Model instance caching for efficiency
- **Temperature Control:** Configurable for parallel generation

### Word Count Requirements
- **Target Range:** 2000-2500 words
- **Rationale:** Optimal LinkedIn article length for engagement
- **Validation:** Automatic word counting and adjustment
- **Quality Balance:** Maintain quality while meeting length constraints

### Integration Requirements
- **Dynamic Criteria Loading:** Must adapt to changes in li_article_judge.py
- **No Modification:** Cannot modify existing li_article_judge.py code
- **Runtime Adaptation:** Detect and adapt to criteria changes automatically
- **Backward Compatibility:** Support existing scoring system interface
- **Model Flexibility:** Support any OpenRouter-compatible model

### Export System Requirements
- **Directory Structure:** Clean organization of versions
- **Conflict Resolution:** Automatic handling of name conflicts
- **Metadata Storage:** Complete version information preserved
- **Format Compatibility:** Standard markdown with front matter
- **Error Recovery:** Robust handling of file operations
- **Auto Mode Support:** Automatic export on target achievement

## Command-Line Interface
```bash
# Component-specific model selection with parallel generation
python main.py \
  --generator-model "openrouter/anthropic/claude-3-sonnet" \
  --judge-model "openrouter/openai/gpt-4o" \
  --rag-model "openrouter/moonshotai/kimi-k2:free" \
  --versions 3 \
  --export-dir "articles/batch1" \
  --outline "Your article outline here"

# Mixed usage with export directory
python main.py \
  --model "openrouter/moonshotai/kimi-k2:free" \
  --judge-model "openrouter/openai/gpt-4o" \
  --export-dir "articles/output" \
  --outline "Your article outline here"
```

### New Command-Line Arguments
- `--generator-model`: Model for article generation and improvement operations
- `--judge-model`: Model for article scoring and evaluation operations  
- `--rag-model`: Model for web search and context retrieval operations
- `--model`: Universal fallback model (backward compatible)
- `--versions`: Number of parallel versions to generate (1-5)
- `--export-dir`: Directory for version export (auto-numbered)
- `--recreate-ctx`: Whether to regenerate RAG context per version

## Development Environment

### Enhanced File Structure
```
/
├── memory-bank/           # Project documentation and context
├── li_article_judge.py    # Existing scoring system (enhanced with model selection)
├── linkedin_article_generator.py  # Article generation (enhanced with parallel support)
├── rag_fast.py            # High-performance async RAG with thread-safe cache
├── context_window_manager.py  # Centralized context window management
├── dspy_factory.py        # Enhanced LLM provider setup with model management
├── main.py                # Enhanced CLI with component-specific model arguments
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (API keys)
└── articles/              # Export directory for generated versions
```

## Quality Assurance

### Enhanced Testing Strategy
- **Unit Tests:** Individual component validation with model selection
- **Integration Tests:** End-to-end article generation with different model combinations
- **Model Selection Tests:** Verify component-specific model assignment
- **Scoring Tests:** Verify scoring system integration with different models
- **Performance Tests:** Measure generation speed and quality across model types
- **Cost Analysis Tests:** Validate cost optimization strategies
- **Fallback Tests:** Ensure graceful degradation when models unavailable
- **Export Tests:** Validate directory management and file operations
- **Cache Tests:** Verify thread safety and atomic operations
- **Parallel Tests:** Validate concurrent generation and version management

### Enhanced Validation Framework
- **Input Validation:** Ensure valid outlines and drafts
- **Model Configuration Validation:** Verify model names and availability
- **Output Validation:** Verify article quality and format
- **Criteria Compliance:** Check adherence to scoring requirements
- **Word Count Compliance:** Validate length constraints
- **Model Performance Validation:** Ensure models perform as expected
- **Cost Validation:** Verify cost optimization is working correctly
- **Export Validation:** Ensure proper file and directory creation
- **Cache Validation:** Verify thread safety and data integrity
- **Version Validation:** Check parallel generation results

## Security Considerations

### API Key Management
- **Environment Variables:** Secure storage in .env file
- **Access Control:** Limit API key exposure
- **Error Handling:** Avoid key leakage in error messages
- **Rotation Support:** Easy API key updates

### Data Privacy
- **Local Processing:** Article content stays local
- **API Calls:** Only necessary data sent to LLM providers
- **Logging:** Avoid sensitive data in logs
- **Cleanup:** Temporary data removal after processing
- **Cache Security:** Protected file operations

## Enhanced Monitoring and Debugging

### Enhanced Logging Strategy
- **Progress Tracking:** Iteration-by-iteration progress with model attribution
- **Model Usage Tracking:** Log which models used for each operation
- **Error Logging:** Comprehensive error capture with model context
- **Performance Metrics:** Generation time and quality trends per model
- **Cost Tracking:** Monitor API usage and costs per model
- **Debug Output:** Detailed intermediate results with model information
- **Fallback Logging:** Track when and why fallbacks are used
- **Export Logging:** Monitor directory and file operations
- **Cache Logging:** Track thread safety and storage efficiency
- **Version Logging:** Monitor parallel generation progress

### Enhanced Metrics Collection
- **Success Rate:** Percentage of articles achieving targets per model combination
- **Iteration Count:** Average iterations to reach goals with different models
- **Quality Trends:** Score improvements over time by model type
- **Performance Benchmarks:** Speed and efficiency metrics per model
- **Cost Metrics:** API usage and cost analysis across model combinations
- **Model Effectiveness:** Track which models perform best for each operation type
- **Export Metrics:** Directory usage and file operation success rates
- **Cache Performance:** Hit rates and storage efficiency
- **Version Metrics:** Parallel generation success and diversity
