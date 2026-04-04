#!/bin/sh

# Interactive LinkedIn Article Generator Script
# Allows user to override main.py default values

echo "=== LinkedIn Article Generator - Interactive Setup ==="
echo

# Default values from main.py
DEFAULT_TARGET_SCORE=89.0
DEFAULT_MAX_ITERATIONS=10
DEFAULT_WORD_MIN=2000
DEFAULT_WORD_MAX=2500
DEFAULT_MODEL="moonshotai/kimi-k2:free"
DEFAULT_GENERATOR_MODEL="moonshotai/kimi-k2:free"
DEFAULT_JUDGE_MODEL="deepseek/deepseek-r1-0528:free"
DEFAULT_RAG_MODEL="deepseek/deepseek-r1-0528:free"
DEFAULT_RECREATE_CTX=false
DEFAULT_QUIET=false
DEFAULT_AUTO=false
DEFAULT_EXPORT_DIR=""
DEFAULT_OUTPUT=""
DEFAULT_EXPORT_RESULTS=""

# Function to read multi-line input
read_multiline() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    echo "$prompt"
    if [ -n "$default" ]; then
        echo "Current default:"
        echo "$default"
        echo
    fi
    echo "Enter your input (press Ctrl+D when finished):"

    # Read until EOF (Ctrl+D)
    local input
    input=$(cat)

    # If empty and no default, keep prompting
    while [ -z "$input" ] && [ -z "$default" ]; do
        echo "This field is required. Please enter a value:"
        input=$(cat)
    done

    # Use default if input is empty
    if [ -z "$input" ] && [ -n "$default" ]; then
        input="$default"
    fi

    eval "$var_name=\"$input\""
}

# Function to read single line with default
read_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    local input
    read -p "$prompt [$default]: " input

    if [ -z "$input" ]; then
        input="$default"
    fi

    eval "$var_name=\"$input\""
}

# Function to read yes/no with default
read_yes_no() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    local default_text
    if [ "$default" = true ]; then
        default_text="Y/n"
    else
        default_text="y/N"
    fi

    local input
    read -p "$prompt ($default_text): " input

    case "$input" in
        [Yy]|[Yy][Ee][Ss])
            eval "$var_name=true"
            ;;
        [Nn]|[Nn][Oo])
            eval "$var_name=false"
            ;;
        "")
            eval "$var_name=$default"
            ;;
        *)
            echo "Invalid input. Using default: $default"
            eval "$var_name=$default"
            ;;
    esac
}

# Get draft (mandatory - no default allowed)
read_multiline "Enter article draft" "" DRAFT

# Get target score
read_with_default "Target score percentage" "$DEFAULT_TARGET_SCORE" TARGET_SCORE

# Get max iterations
read_with_default "Maximum iterations" "$DEFAULT_MAX_ITERATIONS" MAX_ITERATIONS

# Get word count min
read_with_default "Minimum word count" "$DEFAULT_WORD_MIN" WORD_MIN

# Get word count max
read_with_default "Maximum word count" "$DEFAULT_WORD_MAX" WORD_MAX

# Get model settings
read_with_default "Default model" "$DEFAULT_MODEL" MODEL
read_with_default "Generator model" "$DEFAULT_GENERATOR_MODEL" GENERATOR_MODEL
read_with_default "Judge model" "$DEFAULT_JUDGE_MODEL" JUDGE_MODEL
read_with_default "RAG model" "$DEFAULT_RAG_MODEL" RAG_MODEL

# Get flags
read_yes_no "Regenerate RAG context for each version" "$DEFAULT_RECREATE_CTX" RECREATE_CTX
read_yes_no "Quiet mode (suppress progress messages)" "$DEFAULT_QUIET" QUIET
read_yes_no "Auto mode (run without user interaction)" "$DEFAULT_AUTO" AUTO

# Get output options
read_with_default "Export directory (leave empty for none)" "$DEFAULT_EXPORT_DIR" EXPORT_DIR
read_with_default "Output file path (leave empty for none)" "$DEFAULT_OUTPUT" OUTPUT
read_with_default "Export results file (leave empty for none)" "$DEFAULT_EXPORT_RESULTS" EXPORT_RESULTS

echo
echo "=== Configuration Summary ==="
echo "Draft: $(echo "$DRAFT" | head -1 | cut -c1-50)..."
echo "Target Score: $TARGET_SCORE%"
echo "Max Iterations: $MAX_ITERATIONS"
echo "Word Count: $WORD_MIN - $WORD_MAX"
echo "Models: Generator=$GENERATOR_MODEL, Judge=$JUDGE_MODEL, RAG=$RAG_MODEL"
echo "Flags: RecreateCtx=$RECREATE_CTX, Quiet=$QUIET, Auto=$AUTO"
if [ -n "$EXPORT_DIR" ]; then echo "Export Dir: $EXPORT_DIR"; fi
if [ -n "$OUTPUT" ]; then echo "Output File: $OUTPUT"; fi
if [ -n "$EXPORT_RESULTS" ]; then echo "Export Results: $EXPORT_RESULTS"; fi
echo

# Build command
CMD="python main.py --draft \"$DRAFT\" --target-score $TARGET_SCORE --max-iterations $MAX_ITERATIONS --word-count-min $WORD_MIN --word-count-max $WORD_MAX --model \"$MODEL\" --generator-model \"$GENERATOR_MODEL\" --judge-model \"$JUDGE_MODEL\" --rag-model \"$RAG_MODEL\""

if [ "$RECREATE_CTX" = true ]; then CMD="$CMD --recreate-ctx"; fi
if [ "$QUIET" = true ]; then CMD="$CMD --quiet"; fi
if [ "$AUTO" = true ]; then CMD="$CMD --auto"; fi
if [ -n "$EXPORT_DIR" ]; then CMD="$CMD --export-dir \"$EXPORT_DIR\""; fi
if [ -n "$OUTPUT" ]; then CMD="$CMD --output \"$OUTPUT\""; fi
if [ -n "$EXPORT_RESULTS" ]; then CMD="$CMD --export-results \"$EXPORT_RESULTS\""; fi

echo "Executing: $CMD"
echo

# Execute the command
eval "$CMD"
