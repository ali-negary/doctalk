import functools
from typing import Callable

import structlog

# Initialize logger
logger = structlog.get_logger(__name__)


def trace_execution(func: Callable) -> Callable:
    """
    Async decorator to log Token Usage (Cost) and capture Evaluation Data.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 1. Execute the actual function (The LLM generation)
        result = await func(*args, **kwargs)

        try:
            # 2. Extract Data for Metrics
            # We assume 'state' is the second argument (args[1]) in RAGEngine methods
            state = args[1] if len(args) > 1 else {}

            question = state.get("question", "")
            # We convert the list of docs to a string to estimate context size
            context_str = str([d.page_content for d in state.get("documents", [])])
            answer = result.get("generation", "")

            # 3. Calculate "Cost" (Token Estimation)
            # Rule of thumb: 1 token ≈ 4 characters
            input_tokens = (len(question) + len(context_str)) // 4
            output_tokens = len(answer) // 4

            # 4. Fire the "Evaluation Hook" for grading
            logger.info(
                "llm_transaction",
                # METRICS (Cost)
                input_tokens_est=input_tokens,
                output_tokens_est=output_tokens,
                total_tokens_est=input_tokens + output_tokens,
                # EVALUATION HOOK (The Data)
                eval_data={
                    "question": question,
                    "answer_snippet": answer[:100],  # Log snippet for quick view
                    # We log the full context size, but maybe not full text to save log space
                    "context_size_chars": len(context_str),
                },
            )

        except Exception as e:
            # Observability should never crash the app
            logger.warn("observability_failed", error=str(e))

        return result

    return wrapper
