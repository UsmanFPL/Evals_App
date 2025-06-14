"""Evaluation Script
Evaluate AI Overview Responses Against FAQ Knowledge Base (row-by-row).

Usage (example):
    python evaluate_overviews.py \
        --knowledge_csv Help\ (Question-answer)\ -\ new_df.csv \
        --model_csv batch_summary_20250608_155319.csv \
        --output_csv evaluation_results.csv \
        --jwt_token YOUR_JWT_TOKEN_HERE

The script will write an `evaluation_results.csv` that contains the original
`input` and `output` columns plus the 6 quantitative scores and the
`evaluation_justification` returned by the LLM for every row.

Dependencies: pandas, requests, tqdm (optional but recommended).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, Callable, TypeVar, Type

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# Type variable for generic retry decorator
T = TypeVar('T')

# --------------------------- Logging configuration ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --------------------------- Constants  --------------------------------------
API_URL = "https://onegpt.fplinternal.in/api/chat/completions"
MODEL_NAME = "gpt-4o" 

AI_OVERVIEW_CONTEXT = """
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
"""

EVALUATION_CRITERIA = """
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
"""

EVALUATION_INSTRUCTIONS = f"""
{AI_OVERVIEW_CONTEXT}

{EVALUATION_CRITERIA}

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
"""

# --------------------------- Helper functions  ------------------------------

def load_csv(path: str | Path, file_type: str = "knowledge") -> pd.DataFrame:
    """Load a CSV file with flexible column handling.
    
    Args:
        path: Path to the CSV file
        file_type: Type of file ('knowledge' or 'model') to determine expected format
        
    Returns:
        pd.DataFrame: Loaded dataframe with appropriate column names
    """
    try:
        # For knowledge base, we expect 3 columns (question, answer, maybe another question)
        if file_type == "knowledge":
            df = pd.read_csv(path, header=None, names=["question", "answer", "question_alt"])
        # For model outputs, we expect 2 columns (input, output)
        else:
            df = pd.read_csv(path, header=None, names=["input", "output"])
        return df
    except Exception as e:
        raise ValueError(f"Error loading {path}: {str(e)}")


def build_context(knowledge_df: pd.DataFrame) -> str:
    """Format the entire knowledge base into a single text block.
    
    The knowledge base may contain multiple language versions of questions and answers.
    We'll include all of them to provide comprehensive context.
    """
    lines = ["Knowledge Base (multiple language versions may be present for each question):\n"]
    
    # Group by the first column (English question) to handle multi-language entries
    for _, group in knowledge_df.groupby(knowledge_df.columns[0]):
        if isinstance(group, pd.Series):
            group = pd.DataFrame([group])
        
        # Get all unique questions and answers
        questions = set()
        answers = set()
        
        # First column is the English question
        questions.update(group.iloc[:, 0].dropna())
        # Second column is the answer in the same language as the question
        answers.update(group.iloc[:, 1].dropna())
        
        # If there's a third column, it might contain another language version
        if len(group.columns) > 2:
            questions.update(group.iloc[:, 2].dropna())
        
        # Add all questions and answers to the context
        for q in questions:
            lines.append(f"Q: {q}")
        for a in answers:
            lines.append(f"A: {a}")
        lines.append("")  # Add a blank line between entries
    
    return "\n".join(lines)


def build_prompt(
    knowledge_context: str, user_query: str, ai_overview: str
) -> str:
    """Assemble the full prompt to send to the LLM."""
    return f"""
# AI Overview Evaluation Task

## Context
You are evaluating an AI Overview response for OneCard's customer support system. 
The AI Overview should provide clear, accurate, and helpful responses based on the provided knowledge base.

## Knowledge Base
{knowledge_context}

## User Query
{user_query}

## AI-Generated Overview
{ai_overview}

{EVALUATION_INSTRUCTIONS}

## Your Evaluation
Please evaluate the AI Overview response based on the criteria above.

IMPORTANT: Return ONLY a valid JSON object with these exact keys (no other text or formatting):
{{
  "faithfulness_score": <1-5>,
  "relevance_score": <1-5>,
  "completeness_score": <1-5>,
  "helpfulness_score": <1-5>,
  "is_appropriate": <true or false>,
  "is_self_contained": <true or false>,
  "evaluation_justification": "<1-2 sentences>"
}}"""


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (requests.RequestException,),
) -> Callable[..., T]:
    """Retry a function with exponential backoff.
    
    Args:
        func: Function to be retried
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Factor by which the delay should be multiplied each retry
        exceptions: Exceptions to catch and retry on
    """
    def wrapper(*args, **kwargs) -> T:
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt == max_retries:
                    logger.error("Max retries (%d) reached. Last error: %s", max_retries, e)
                    raise
                
                # Add jitter to avoid thundering herd problem
                sleep_time = delay * (1 + random.random() * 0.1)  # 0-10% jitter
                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt + 1, max_retries, str(e), sleep_time
                )
                time.sleep(sleep_time)
                delay *= backoff_factor
        
        # This line should theoretically never be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in retry logic") from last_exception
    
    return wrapper


def create_http_session(retries: int = 3) -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


@retry_with_backoff
def call_llm(
    prompt: str,
    token: str,
    model: str = MODEL_NAME,
    session: Optional[requests.Session] = None,
    timeout: int = 300
) -> str:
    """Call the LLM API with retry logic and return the assistant's content text."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }
    
    request_fn = session.post if session else requests.post
    response = request_fn(
        API_URL,
        headers=headers,
        json=payload,
        timeout=timeout
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def safe_json_parse(raw_response: str) -> Dict[str, Any]:
    """Attempt to parse the assistant's response as JSON.

    The model might wrap JSON in code fences or text; attempt to extract the first
    JSON object found.
    """
    raw_response = raw_response.strip()
    # Remove code fences if present
    if raw_response.startswith("```"):
        raw_response = raw_response.strip("`\n")
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        # Fallback: try to find first {...} substring
        import re

        match = re.search(r"{.*}", raw_response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError("Unable to parse JSON from LLM response")


# --------------------------- Main evaluation loop ---------------------------

def process_single_row(
    row: pd.Series,
    knowledge_context: str,
    token: str,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """Process a single row of the model output."""
    result = {}
    user_query = str(row["input"])
    ai_overview = str(row["output"])
    prompt = build_prompt(knowledge_context, user_query, ai_overview)

    try:
        assistant_text = call_llm(prompt, token, session=session)
        parsed = safe_json_parse(assistant_text)
        result.update(parsed)
    except Exception as e:
        logger.error("Error processing row: %s", e)
        result["evaluation_justification"] = f"Error: {e}"
    
    return result


def evaluate_rows(
    knowledge_df: pd.DataFrame,
    model_df: pd.DataFrame,
    token: str,
    max_workers: int = 3,
) -> pd.DataFrame:
    """Evaluate each row in parallel and return a new DataFrame with added columns.
    
    Args:
        knowledge_df: DataFrame containing the knowledge base
        model_df: DataFrame containing model inputs and outputs to evaluate
        token: API token for the LLM
        max_workers: Maximum number of parallel API calls
        
    Returns:
        DataFrame with evaluation results
    """
    knowledge_context = build_context(knowledge_df)
    result_df = model_df.copy()
    
    # Initialize result columns with updated boolean field names
    scores_columns = [
        "is_appropriate",
        "is_self_contained",
        "faithfulness_score",
        "relevance_score",
        "completeness_score",
        "helpfulness_score",
        "evaluation_justification",
    ]
    
    for col in scores_columns:
        result_df[col] = None
    
    # Create a session for connection pooling
    with create_http_session() as session:
        # Create a partial function with the common parameters
        process_func = partial(
            process_single_row,
            knowledge_context=knowledge_context,
            token=token,
            session=session,
        )
        
        # Process rows in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_idx = {
                executor.submit(process_func, row): idx
                for idx, row in model_df.iterrows()
            }
            
            # Process results as they complete
            for future in tqdm(
                as_completed(future_to_idx),
                total=len(future_to_idx),
                desc="Evaluating",
                unit="row"
            ):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    for key, value in result.items():
                        if key in result_df.columns:
                            result_df.at[idx, key] = value
                except Exception as e:
                    logger.error("Error processing row %s: %s", idx, e)
                    result_df.at[idx, "evaluation_justification"] = f"Error: {e}"
    
    return result_df


# --------------------------- CLI interface ----------------------------------

def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate AI overviews against FAQ knowledge base.")
    parser.add_argument("--knowledge_csv", required=True, help="Path to FAQ knowledge base CSV (with 'question','answer' columns)")
    parser.add_argument("--model_csv", required=True, help="Path to model output CSV (with 'input','output' columns)")
    parser.add_argument("--output_csv", default="evaluation_results.csv", help="Destination for evaluated CSV")
    parser.add_argument("--jwt_token", default=os.getenv("ONEGPT_TOKEN"), help="JWT token for the LLM API. Can also be set via ONEGPT_TOKEN env var.")
    parser.add_argument("--max_workers", type=int, default=3, help="Maximum number of parallel API calls (default: 3)")
    parser.add_argument("--timeout", type=int, default=120, help="API request timeout in seconds (default: 120)")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    start_time = time.time()
    args = parse_args(argv)
    
    if not args.jwt_token:
        logger.error("JWT token not provided (via --jwt_token or ONEGPT_TOKEN)")
        sys.exit(1)

    try:
        # Load knowledge base (expecting 3 columns: question, answer, question_alt)
        knowledge_df = load_csv(args.knowledge_csv, file_type="knowledge")
        # Load model outputs (expecting 2 columns: input, output)
        model_df = load_csv(args.model_csv, file_type="model")

        logger.info("Loaded knowledge base with %d rows and model outputs with %d rows", 
                   len(knowledge_df), len(model_df))
        logger.info("Starting evaluation with %d workers (timeout: %ds)", 
                   args.max_workers, args.timeout)
        
        # Set global timeout for call_llm
        global LLM_TIMEOUT
        LLM_TIMEOUT = args.timeout

        evaluated_df = evaluate_rows(
            knowledge_df, 
            model_df, 
            args.jwt_token,
            max_workers=args.max_workers
        )

        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
        evaluated_df.to_csv(args.output_csv, index=False)
        
        elapsed = time.time() - start_time
        logger.info("Evaluation completed in %.1f seconds", elapsed)
        logger.info("Results written to %s", os.path.abspath(args.output_csv))
        
    except Exception as e:
        logger.exception("An error occurred during evaluation")
        sys.exit(1)


if __name__ == "__main__":
    main()
