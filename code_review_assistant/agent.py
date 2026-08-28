"""
Main agent orchestration for the Code Review Assistant.

This module defines a comprehensive code review assistant that analyzes
Python code and provides detailed feedback through a multi-stage pipeline.

The root agent acts as the single entry point for user interaction and
routes review requests through the specialized sub-agents below.
"""

# Import the ADK agent classes used to compose the assistant.
from google.adk.agents import Agent, SequentialAgent

# Shared runtime configuration for model selection.
from .config import config

# Import each specialized review sub-agent.
from code_review_assistant.sub_agents.review_pipeline.code_analyzer import (
    code_analyzer_agent,
)

from code_review_assistant.sub_agents.review_pipeline.style_checker import (
    style_checker_agent,
)

from code_review_assistant.sub_agents.review_pipeline.test_runner import (
    test_runner_agent,
)

from code_review_assistant.sub_agents.review_pipeline.feedback_synthesizer import (
    feedback_synthesizer_agent,
)

# Create a sequential pipeline so each review step runs in order.
# The analysis phase is followed by style checks, then test execution,
# and finally feedback synthesis.
code_review_pipeline = SequentialAgent(
    name="CodeReviewPipeline",

    description=(
        "Complete code review pipeline with "
        "analysis, testing, and feedback"
    ),

    sub_agents=[
        code_analyzer_agent,
        style_checker_agent,
        test_runner_agent,
        feedback_synthesizer_agent
    ]
)


# Root agent used by the application to handle user requests.
# It delegates code review work to the full pipeline and returns the
# final synthesized feedback back to the caller.
root_agent = Agent(
    name="CodeReviewAssistant",

    model=config.worker_model,

    description=(
        "An intelligent code review assistant "
        "that analyzes Python code and provides "
        "educational feedback"
    ),

    instruction="""
You are a specialized Python code review assistant.

When a user provides Python code for review:

1. Immediately delegate to CodeReviewPipeline.

2. Pass the Python code EXACTLY as the user provided it.

3. Let the pipeline perform all analysis,
   testing, and feedback synthesis.

4. Return ONLY the final feedback generated
   by the pipeline.

When a user asks general questions:

- Explain your code-review capabilities.
- Do NOT trigger the review pipeline unless
  Python code was submitted for review.
""",

    sub_agents=[
        code_review_pipeline
    ],

    output_key="assistant_response"
)


# The fix loop and follow-up workflow would be attached here if this
# stage of the project evolves beyond a single review pass.
# MODULE_6_STEP_5_CREATE_FIX_LOOP


# MODULE_6_STEP_5_UPDATE_ROOT_AGENT