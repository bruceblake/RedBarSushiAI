# LLM Prompt Evaluation Framework

This module provides a comprehensive framework for evaluating and improving LLM prompts used in the RedBarSushiAI system.

## Overview

The LLM Prompt Evaluation Framework helps ensure that prompts used for intent detection, response generation, and function calling are effective and accurate. It includes:

1. **Test Cases**: Structured test cases covering all prompt types
2. **Evaluator**: Automated evaluation against expected outputs
3. **Analyzer**: Failure analysis and improvement suggestions
4. **CLI Tools**: Command-line interface for running evaluations

## Components

### 1. Test Cases (`prompt_test_cases.py`)

Defines test cases across multiple categories:
- **Intent Detection**: Tests for FSM state-based intent detection
- **Agent Response**: Tests for appropriate agent responses
- **Function Calling**: Tests for correct function invocation
- **Disambiguation**: Tests for handling ambiguous requests
- **Global Commands**: Tests for global command detection

### 2. Evaluator (`prompt_evaluator.py`)

Runs test cases against actual LLM responses:
- Supports multiple OpenAI models
- Concurrent evaluation for performance
- Detailed result tracking with timing
- CSV and JSON output formats

### 3. Improvement Analyzer (`prompt_improvement_analyzer.py`)

Analyzes failures and suggests prompt improvements:
- Groups failures by pattern
- Generates specific improvement suggestions
- Estimates impact on pass rate
- Outputs both JSON and Markdown reports

## Usage

### Running a Full Evaluation

```bash
# Run all tests
python tests/llm_evaluation/run_prompt_evaluation.py

# Run specific categories
python tests/llm_evaluation/run_prompt_evaluation.py --categories intent_detection agent_response

# Run tests with specific tags
python tests/llm_evaluation/run_prompt_evaluation.py --tags greeting ordering

# Use a different model
python tests/llm_evaluation/run_prompt_evaluation.py --model gpt-4o
```

### Running a Single Test

```bash
# Run a specific test by ID
python tests/llm_evaluation/run_prompt_evaluation.py --test-id intent_greeting_001
```

### Listing Available Tests

```bash
# List all available test cases
python tests/llm_evaluation/run_prompt_evaluation.py --list-tests
```

### Analyzing Results

After running an evaluation, analyze the results:

```bash
# Analyze a specific evaluation report
python tests/llm_evaluation/prompt_improvement_analyzer.py test_results/prompt_evaluation_report_20240115_120000.json
```

This generates:
- `prompt_improvements.json`: Structured improvement suggestions
- `prompt_improvements.md`: Human-readable markdown report

## Test Case Structure

Each test case includes:
- **ID**: Unique identifier
- **Category**: Type of test (intent, response, etc.)
- **Description**: What the test validates
- **System Prompt**: The prompt being tested
- **User Input**: Sample user input
- **Context**: Additional context (FSM state, etc.)
- **Expected Outputs**: Acceptable responses
- **Tags**: For filtering tests

## Evaluation Metrics

The evaluator tracks:
- **Pass Rate**: Overall and by category
- **Execution Time**: Per test and average
- **Confidence Scores**: For probabilistic outputs
- **Failure Patterns**: Common failure modes

## Improvement Process

1. **Run Evaluation**: Execute tests against current prompts
2. **Analyze Failures**: Use the analyzer to identify patterns
3. **Review Suggestions**: Examine the improvement report
4. **Update Prompts**: Implement suggested changes
5. **Re-evaluate**: Run tests again to verify improvements

## Adding New Test Cases

To add new test cases:

1. Edit `prompt_test_cases.py`
2. Add to the appropriate test class (e.g., `IntentDetectionTestCases`)
3. Follow the existing pattern for test structure
4. Include relevant tags for filtering

Example:
```python
PromptTestCase(
    id="intent_new_001",
    category=TestCategory.INTENT_DETECTION,
    description="User asks about allergies",
    system_prompt="",  # Will use default from intent detector
    user_input="I have a nut allergy",
    context={"state": "ORDERING"},
    expected_outputs=["ALLERGY_INFO"],
    expected_intent="ALLERGY_INFO",
    tags=["ordering", "allergy", "dietary"]
)
```

## Best Practices

1. **Regular Evaluation**: Run evaluations after prompt changes
2. **Baseline Tracking**: Save evaluation reports for comparison
3. **Iterative Improvement**: Make small, targeted improvements
4. **Model Testing**: Test prompts with different models
5. **Real-World Validation**: Validate improvements with actual usage

## Output Files

- `test_results/prompt_evaluation_TIMESTAMP.csv`: Detailed test results
- `test_results/prompt_evaluation_report_TIMESTAMP.json`: Summary report
- `test_results/prompt_improvements.json`: Improvement suggestions
- `test_results/prompt_improvements.md`: Human-readable improvements

## Integration with CI/CD

The evaluation can be integrated into CI/CD pipelines:

```bash
# Exit with error code if tests fail
python tests/llm_evaluation/run_prompt_evaluation.py --quiet

# Check specific pass rate threshold
# (Implement in your CI script based on the JSON report)
```

## Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure `OPENAI_API_KEY` is set
2. **Rate Limiting**: Reduce batch size in evaluator
3. **Timeout Errors**: Increase timeout for complex prompts
4. **Import Errors**: Run from project root or adjust Python path

### Debug Mode

For detailed debugging:
```python
# In your test script
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

Potential improvements to the framework:
1. A/B testing for prompt variations
2. Integration with production metrics
3. Automatic prompt optimization
4. Multi-language support testing
5. Adversarial test generation