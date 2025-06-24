# Disambiguation Logic Documentation

## Overview
The disambiguation system handles ambiguous menu item requests by detecting when multiple items match a user's query and guiding them to clarify their choice.

## Architecture

### Core Components

1. **DisambiguationDetector** (`app/utils/disambiguation.py`)
   - Analyzes match results to determine if clarification is needed
   - Configurable thresholds for similarity and ambiguity
   - Identifies disambiguation type (multiple exact, similar names, category, etc.)

2. **DisambiguationResolver** (`app/utils/disambiguation.py`)
   - Generates natural language clarification questions
   - Matches user responses to candidate items
   - Supports various response types (name, price, position, category)

3. **Agent Integration**
   - Menu Agent: Detects ambiguity when looking up items
   - Cart Agent: Handles disambiguation during order building
   - Both maintain disambiguation context for multi-turn clarification

### Disambiguation Types

1. **MULTIPLE_EXACT**: Multiple items with the same name
   - Example: "California Roll" at different price points
   - Clarification: Price-based or description-based

2. **SIMILAR_NAMES**: Items with similar but not identical names
   - Example: "salmon" matches "Salmon Roll", "Salmon Nigiri", "Salmon Sashimi"
   - Clarification: Category or full name based

3. **CATEGORY_AMBIGUOUS**: User mentions a broad category
   - Example: "I want sushi" (many options)
   - Clarification: List top options from category

4. **MODIFIER_AMBIGUOUS**: Ambiguous modifier reference
   - Example: "Make it spicy" (which item?)
   - Future enhancement

## Detection Logic

### Thresholds
- **Similarity Threshold** (0.7): Minimum confidence to consider an item
- **Ambiguity Threshold** (0.85): Maximum confidence difference between top matches

### Detection Algorithm
```python
1. Filter matches above similarity threshold
2. If multiple exact matches (confidence >= 0.95): MULTIPLE_EXACT
3. If top two matches are within ambiguity threshold: SIMILAR_NAMES
4. If query contains category term and many matches: CATEGORY_AMBIGUOUS
5. Otherwise: No disambiguation needed
```

## Resolution Strategies

### Clarification Generation
Different strategies based on disambiguation type:

1. **Price Disambiguation**
   - "Did you want the one for $12.00 or the one for $14.00?"
   
2. **Category Disambiguation**
   - "Did you mean the Salmon Roll from our rolls menu, or the Salmon Nigiri?"
   
3. **List Disambiguation**
   - "I found several options. Did you mean: California Roll, Spicy California, or California Deluxe?"

### Response Matching
The resolver can understand various response types:

1. **Price Match**: "$12", "the cheaper one", "14 dollars"
2. **Category Match**: "the roll", "from appetizers"
3. **Name Match**: Full or partial item names
4. **Position Match**: "first one", "the second", "last one"

## Implementation Flow

### Menu/Cart Agent Flow
```
1. User: "I want salmon"
2. Agent: Calls lookup_menu_item("salmon")
3. Matcher: Finds multiple matches
4. Detector: Determines disambiguation needed
5. Agent: Returns clarification question
6. User: "The roll please"
7. Agent: Calls resolve_disambiguation("the roll please")
8. Resolver: Matches to Salmon Roll
9. Agent: Proceeds with Salmon Roll
```

### Context Persistence
- Disambiguation context stored in agent instance
- Survives multiple turns of conversation
- Maximum 2 attempts before giving up
- Clears after successful resolution

## Usage Examples

### Example 1: Multiple Types
```
User: "I'd like salmon"
System: "I found several salmon options. Did you mean the Salmon Roll for $12.00, 
         the Salmon Nigiri for $8.00, or the Salmon Sashimi for $14.00?"
User: "The roll"
System: "Great! I've added a Salmon Roll to your order."
```

### Example 2: Similar Names
```
User: "California roll"
System: "Did you mean the California Roll or the California Deluxe Roll?"
User: "The regular one"
System: "Perfect! Adding California Roll to your order."
```

### Example 3: Price-Based Resolution
```
User: "I want the tuna"
System: "I found two tuna options. Did you want the one for $13.00 
         or the one for $16.00?"
User: "The $16 one"
System: "Excellent choice! I've added the Tuna Special Roll."
```

## Configuration

### Thresholds (in DisambiguationDetector)
```python
similarity_threshold = 0.7  # Minimum match confidence
ambiguity_threshold = 0.85  # Maximum confidence gap
```

### Attempts (in DisambiguationContext)
```python
max_attempts = 2  # Maximum clarification attempts
```

### Candidate Limits
```python
max_candidates = 3  # For SIMILAR_NAMES
max_candidates = 5  # For CATEGORY_AMBIGUOUS
```

## Best Practices

1. **Natural Language**: Use conversational clarification questions
2. **Limit Options**: Don't overwhelm with too many choices (max 3-5)
3. **Clear Differences**: Highlight distinguishing features (price, category)
4. **Graceful Failure**: After max attempts, ask for more specific input
5. **Context Aware**: Remember disambiguation state across turns

## Future Enhancements

1. **Learning**: Track successful resolutions to improve matching
2. **Preferences**: Remember user preferences (always picks rolls)
3. **Smart Ordering**: Order candidates by popularity or user history
4. **Voice Optimization**: Shorter clarifications for voice interface
5. **Multi-Item**: Handle "I want both" responses