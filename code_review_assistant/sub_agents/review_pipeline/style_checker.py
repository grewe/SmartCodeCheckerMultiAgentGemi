"""
Style Checker Agent - Validates PEP 8 compliance.

This agent checks Python code style against PEP 8 guidelines using
pycodestyle, identifying violations and calculating a style score. It runs
after the structural analysis step and before test execution.
"""

# Import the ADK agent utilities and the style-checking tool.
from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool
from google.adk.utils import instructions_utils
from code_review_assistant.config import config
from code_review_assistant.tools import check_code_style


# This instruction provider injects the current review state into the prompt so
# the agent can compare style findings with the earlier structural analysis.
# MODULE_5_STEP_1_INSTRUCTION_PROVIDER
async def style_checker_instruction_provider(
    context: ReadonlyContext
) -> str:

    template = """
You are a code style expert focused on PEP 8 compliance.

Your task:

1. Use the check_code_style tool to validate PEP 8 compliance.

2. The tool will retrieve the ORIGINAL code from state automatically.

3. Report violations exactly as found.

4. Present the results clearly and confidently.

CRITICAL:

- The tool checks the code EXACTLY as provided by the user.
- Do not suggest that the code was modified or fixed.
- Report actual violations found in the original code.
- If there are style issues, report them honestly.

Call the check_code_style tool with an empty string
for the code parameter because the tool will retrieve
the original code from shared state automatically.

When presenting the tool results:

- State the exact score returned by the tool.

- If score >= 90:
  "Excellent style compliance!"

- If score is 70-89:
  "Good style with minor improvements needed"

- If score is 50-69:
  "Style needs attention"

- If score < 50:
  "Significant style improvements needed"

List the specific violations found:

- Show line numbers
- Show error codes
- Show messages
- Focus on the top 10 issues

Previous structural analysis:

{structure_analysis_summary}

Format your response as:

## Style Analysis Results

- Style Score: [exact score]/100
- Total Issues: [count]
- Assessment: [assessment based on score]

## Top Style Issues

[List issues with line numbers and descriptions]

## Recommendations

[Specific fixes for the most important issues]
"""

    return await (
        instructions_utils.inject_session_state(
            template,
            context
        )
    )

# Style checker agent that runs the PEP 8 validation step and stores the result.
# MODULE_5_STEP_1_STYLE_CHECKER_AGENT
style_checker_agent = Agent(
    name="StyleChecker",

    model=config.worker_model,

    description=(
        "Checks Python code style against "
        "PEP 8 guidelines"
    ),

    instruction=style_checker_instruction_provider,

    tools=[
        FunctionTool(
            func=check_code_style
        )
    ],

    output_key="style_check_summary"
)