# AI Overview Evaluation Framework

## Overview
This framework evaluates the quality of AI-generated overviews in the OneCard help section. The AI Overview provides instant, accurate responses to customer queries by summarizing relevant information from the FAQ knowledge base.

## Purpose
Evaluate the effectiveness of AI-generated overviews based on:
1. Accuracy and faithfulness to the source material
2. Relevance to user queries
3. Completeness of information
4. Helpfulness in addressing user needs
5. Appropriateness for the help section context

## Evaluation Criteria

### 1. Faithfulness (1-5)
- **5**: Perfectly matches the knowledge base without additions or contradictions
- **3**: Mostly accurate but may have minor inaccuracies or omissions
- **1**: Contains significant inaccuracies or fabrications

### 2. Relevance (1-5)
- **5**: Directly addresses the user's specific query
- **3**: Somewhat relevant but includes tangential information
- **1**: Not relevant to the user's question

### 3. Completeness (1-5)
- **5**: Includes all key information needed to answer the query
- **3**: Missing some useful details but answers the main question
- **1**: Missing critical information needed to address the query

### 4. Helpfulness (1-5)
- **5**: Provides a clear, actionable, and complete response
- **3**: Somewhat helpful but could be clearer or more complete
- **1**: Not helpful or confusing

### 5. Appropriateness (Boolean)
- **True**: The response is appropriate for a text-only overview
- **False**: The response requires UI elements or additional context not provided

### 6. Self-Contained (Boolean)
- **True**: The response is complete and doesn't require follow-up
- **False**: The response asks for more information or is incomplete

## Model and Infrastructure

### Evaluation Model
- **Model Name**: `o1` (OpenAI reasoning model)
- **API Endpoint**: `https://onegpt.fplinternal.in/api/chat/completions`
- **Authentication**: JWT token-based authentication
- **Request Timeout**: 300 seconds (configurable)
- **Concurrency**: Up to 5 parallel requests (configurable)

### Model Configuration
- **Temperature**: 0 (for consistent, deterministic outputs)
- **Max Tokens**: 1024 (sufficient for detailed evaluations)
- **Top-p (nucleus)**: 0.9 (for balanced creativity and precision)

## Exact Prompt Template

Below is the exact prompt template used for evaluation. The placeholders in angle brackets (`< >`) are replaced with actual values during execution:

```
# AI Overview Evaluation Task

## Context
You are evaluating an AI Overview response for OneCard's customer support system. 
The AI Overview should provide clear, accurate, and helpful responses based on the provided knowledge base.

## Knowledge Base
<Knowledge base content goes here>

## User Query
<User's query goes here>

## AI-Generated Overview
<AI's response goes here>

## AI Overview Product Context
You are evaluating responses from an AI Overview system designed for OneCard, a financial services platform. 
The AI Overview provides instant, accurate, and helpful responses to customer queries by summarizing relevant information 
from the knowledge base.

### User Experience
- The AI Overview appears at the top of the help section when users search for a query
- Below the overview, users see a list of relevant FAQ links that they can tap to view detailed answers
- The overview should provide enough information to answer common queries while encouraging users to explore the full FAQs for more details

### Response Guidelines
The AI Overview should:
1. Provide clear, concise, and accurate information
2. Be helpful and actionable for customers
3. Maintain a professional and friendly tone
4. Only use information from the provided knowledge base
5. Avoid making assumptions or providing false information
6. Be self-contained while complementing the FAQ links below it

## Response Format
AI Overview responses should be:
- Self-contained (no need to reference the knowledge base or external sources)
- Direct and to the point
- Free of technical jargon unless explained
- Structured for easy reading
- Limited to 2-3 sentences when possible

## Evaluation Criteria

1. Faithfulness (1-5):
   - 5: Perfectly matches the knowledge base without additions or contradictions
   - 3: Mostly accurate but may have minor inaccuracies or omissions
   - 1: Contains significant inaccuracies or fabrications

2. Relevance (1-5):
   - 5: Directly addresses the user's specific query
   - 3: Somewhat relevant but may include tangential information
   - 1: Not relevant to the user's question

3. Completeness (1-5):
   - 5: Includes all key information needed to answer the query
   - 3: Missing some useful details but still answers the main question
   - 1: Missing critical information needed to address the query

4. Helpfulness (1-5):
   - 5: Provides a clear, actionable, and complete response
   - 3: Somewhat helpful but could be clearer or more complete
   - 1: Not helpful or confusing

5. Appropriateness (true/false):
   - true: The response is appropriate for a text-only overview
   - false: The response requires UI elements or additional context not provided

6. Self-Contained (true/false):
   - true: The response is complete and doesn't require follow-up
   - false: The response asks for more information or is incomplete

## Evaluation Task
For the given user query and AI-generated overview, evaluate the response based on the criteria above.

## Instructions
1. Read the AI Overview Product Context and Evaluation Criteria carefully
2. Compare the AI's response to the provided knowledge base
3. Assign scores for each criterion
4. Provide a brief justification for your scores
5. Return ONLY a valid JSON object with these exact keys:
   - faithfulness_score (1-5)
   - relevance_score (1-5)
   - completeness_score (1-5)
   - helpfulness_score (1-5)
   - is_appropriate (boolean)
   - is_self_contained (boolean)
   - evaluation_justification (string, 1-2 sentences)

Do not include any additional keys or comments. Evaluate THIS ROW ONLY.

## Your Evaluation
Please evaluate the AI Overview response based on the criteria above.

IMPORTANT: Return ONLY a valid JSON object with these exact keys (no other text or formatting):
{
  "faithfulness_score": <1-5>,
  "relevance_score": <1-5>,
  "completeness_score": <1-5>,
  "helpfulness_score": <1-5>,
  "is_appropriate": <true or false>,
  "is_self_contained": <true or false>,
  "evaluation_justification": "<1-2 sentences>"
}
```

## Prompt Structure

The evaluation prompt is carefully constructed to ensure consistent and accurate evaluations. It follows this structure:

### 1. Task Context
```
# AI Overview Evaluation Task

## Context
[AI Overview Product Context]
[Evaluation Criteria]
```

### 2. Knowledge Base
```
## Knowledge Base
[Relevant FAQ entries from the knowledge base]
```

### 3. User Query & AI Response
```
## User Query
[The original user query]

## AI-Generated Overview
[The AI's response to evaluate]
```

### 4. Evaluation Instructions
```
## Your Evaluation
[Detailed evaluation criteria and format requirements]
```

### 5. Expected Output Format
```json
{
  "faithfulness_score": 1-5,
  "relevance_score": 1-5,
  "completeness_score": 1-5,
  "helpfulness_score": 1-5,
  "is_appropriate": true/false,
  "is_self_contained": true/false,
  "evaluation_justification": "1-2 sentence explanation"
}
```

## Technical Implementation

### Prompt Engineering Details

#### Key Prompt Components
1. **System Context**: Sets the role and expectations for the evaluator
2. **Evaluation Criteria**: Detailed scoring guidelines for each metric
3. **Knowledge Grounding**: Relevant FAQ entries to verify information against
4. **Structured Output**: Clear JSON format requirements
5. **Error Prevention**: Explicit instructions to avoid common mistakes

#### Handling Edge Cases
- **Missing Information**: How to handle when knowledge base is incomplete
- **Ambiguous Queries**: Guidelines for interpreting unclear user questions
- **Multiple Valid Interpretations**: How to score when multiple answers could be correct
- **Sensitive Content**: Instructions for handling inappropriate queries

### Data Flow
1. **Input**: 
   - FAQ Knowledge Base (CSV)
   - AI-Generated Overviews (CSV with queries and responses)

2. **Processing**:
   - Loads and parses both datasets
   - For each query-response pair:
     - Retrieves relevant FAQ context
     - Builds an evaluation prompt
     - Sends to the evaluation LLM
     - Parses and records the results

3. **Output**:
   - CSV file with original queries, AI responses, and evaluation scores
   - Summary statistics and metrics

### Key Components
- `evaluate_overviews.py`: Main evaluation script
- `LLM_connection_test.py`: LLM API interaction utilities
- Input CSVs:
  - `Help (Question-answer) - new_df.csv`: FAQ knowledge base
  - `Evals_input_batch_summary_*.csv`: AI-generated responses to evaluate

## Usage

### Prerequisites
- Python 3.8+

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/UsmanFPL/Evals.git
   cd Evals
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Evaluation
```bash
python evaluate_overviews.py \
  --knowledge_csv "path/to/knowledge_base.csv" \
  --model_csv "path/to/ai_responses.csv" \
  --output_csv "evaluation_results.csv" \
  --jwt_token "your_jwt_token_here" \
  --max_workers 5 \
  --timeout 300
```

### Command Line Arguments
- `--knowledge_csv`: Path to the FAQ knowledge base CSV (required)
- `--model_csv`: Path to the AI-generated responses CSV (required)
- `--output_csv`: Path to save evaluation results (default: "evaluation_results.csv")
- `--jwt_token`: JWT token for API authentication (can also be set via ONEGPT_TOKEN env var)
- `--max_workers`: Number of parallel evaluation workers (default: 3)
- `--timeout`: API request timeout in seconds (default: 120)

### Example Command
```bash
python evaluate_overviews.py \
  --knowledge_csv "Help (Question-answer) - new_df.csv" \
  --model_csv "Evals_input_batch_summary_20250608_155319.csv" \
  --output_csv "evaluation_results_full.csv" \
  --jwt_token "your_jwt_token_here" \
  --max_workers 5 \
  --timeout 300
```

## Results Interpretation

### Output Columns
- `input`: Original user query
- `output`: AI-generated response
- `faithfulness_score`: 1-5 rating
- `relevance_score`: 1-5 rating
- `completeness_score`: 1-5 rating
- `helpfulness_score`: 1-5 rating
- `is_appropriate`: true/false
- `is_self_contained`: true/false
- `evaluation_justification`: Brief explanation of the scores

### Analysis
- **High Scores (4-5)**: Indicate strong performance in that criterion
- **Medium Scores (2-3)**: Suggest room for improvement
- **Low Scores (1)**: Indicate significant issues that need addressing
- **Boolean Fields**: Should ideally be `true` for most responses

## Best Practices

### For Evaluators
1. Consider the user's perspective when scoring
2. Be consistent in your evaluations
3. Provide clear justifications for scores
4. Flag any systematic issues in the AI's responses

### For Developers
1. Monitor evaluation metrics over time
2. Look for patterns in low-scoring responses
3. Use results to guide model improvements
4. Regularly update the knowledge base based on findings

## Future Enhancements
1. Add more detailed analytics and visualization
2. Implement automated alerts for quality issues
3. Expand evaluation criteria based on user feedback
4. Add support for different languages and locales
