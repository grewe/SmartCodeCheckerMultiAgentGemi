"""
Feedback Synthesizer Agent - Provides comprehensive, personalized feedback.

This agent synthesizes all analysis results into constructive feedback,
incorporating past feedback history and tracking improvement over time.
It is the final stage of the review pipeline and produces the user-facing
summary.
"""

# Import the agent framework, session context utilities, and feedback tools.
from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from google.adk.utils import instructions_utils
from code_review_assistant.config import config
from code_review_assistant.tools import search_past_feedback, update_grading_progress, save_grading_report


# This helper builds a dynamic instruction string using the state from earlier
# pipeline steps, such as structure findings, style issues, and test results.
# MODULE_5_STEP_4_INSTRUCTION_PROVIDER
async def feedback_instruction_provider(
    context: ReadonlyContext
) -> str:

    template = """
You are an expert code reviewer and mentor providing
constructive, educational feedback.

CONTEXT FROM PREVIOUS AGENTS:

- Structure analysis summary:
  {structure_analysis_summary}

- Style check summary:
  {style_check_summary}

- Test execution summary:
  {test_execution_summary}

YOUR TASK requires these steps IN ORDER:

1. Call search_past_feedback with
   developer_id="default_user".

2. Call update_grading_progress with no parameters.

3. Carefully analyze the test results.

4. Generate comprehensive feedback.

5. Call save_grading_report with the completed
   feedback as feedback_text.

6. Return the feedback as your final output.

CRITICAL - Understanding Test Results:

- tests_passed means the code worked correctly.
- tests_failed means the code returned incorrect output.
- tests_with_errors means the code crashed.
- critical_issues means serious bugs were found.

Do NOT treat discovering a bug as a successful test.

Use this feedback structure:

## Summary

Provide an honest overall assessment.

## Strengths

List 2-3 specific strengths.

## Code Quality Analysis

### Structure & Organization

Discuss organization, readability, and documentation.

### Style Compliance

Report the actual style score and important issues.

### Test Results

Report actual test results accurately.
If critical issues exist, identify them clearly.

## Recommendations for Improvement

Provide specific, actionable fixes.

## Next Steps

Give a prioritized action list.

## Encouragement

End constructively while remaining accurate.

Remember to complete all required tool calls,
including save_grading_report.
"""

    return await (
        instructions_utils.inject_session_state(
            template,
            context
        )
    )

# Final synthesis agent that gathers earlier review output and formats a
# polished assessment for the user.
# MODULE_5_STEP_4_SYNTHESIZER_AGENT
feedback_synthesizer_agent = Agent(
    name="FeedbackSynthesizer",

    model=config.critic_model,

    description=(
        "Synthesizes all analysis into "
        "constructive, personalized feedback"
    ),

    instruction=feedback_instruction_provider,

    tools=[
        FunctionTool(
            func=search_past_feedback
        ),
        FunctionTool(
            func=update_grading_progress
        ),
        FunctionTool(
            func=save_grading_report
        )
    ],

    output_key="final_feedback"
)