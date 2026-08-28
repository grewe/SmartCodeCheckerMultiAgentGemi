"""
Code Analyzer Agent - Understands code structure and complexity.

This agent is responsible for parsing and analyzing Python code structure,
identifying functions, classes, imports, and potential issues. It acts as
an initial review step before the style and test checks run.
"""

# Import the agent framework and the tool that inspects Python structure.
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from code_review_assistant.config import config
from code_review_assistant.tools import analyze_code_structure


# This specialized agent performs the static structure review.
# It should inspect the submitted source without executing user code.
# MODULE_4_STEP_5_CREATE_AGENT
code_analyzer_agent = Agent(
    name="CodeAnalyzer",

    model=config.worker_model,

    description=(
        "Analyzes Python code structure and identifies "
        "functions, classes, imports, and structural metrics."
    ),

    instruction="""
    You are a specialized Python code structure analysis agent.

    You MUST analyze the EXACT Python source code supplied by the user.

    IMPORTANT TOOL RULES:
    - You MUST use the analyze_code_structure tool.
    - analyze_code_structure is the ONLY tool you may use.
    - NEVER use Python code execution.
    - NEVER request python_interpreter.
    - NEVER request google:python_interpreter.
    - NEVER attempt to execute the submitted code.

    Pass the source code exactly as supplied to analyze_code_structure.

    Do NOT:
    - repair syntax
    - change indentation
    - rewrite the code
    - execute the code
    - invent structural information

    After the tool returns, summarize:
    - functions
    - classes
    - methods
    - imports
    - docstrings
    - arguments
    - structural metrics
    - structural or syntax problems reported by the tool
    """,

    
    # The earlier instruction string is intentionally commented out as a
    # historical alternative. Keeping it here documents the agent's design.
    #instruction="""
    #You are a specialized Python code analysis agent.

    #Your responsibility is to analyze the EXACT Python
    #source code supplied by the user.

    #You MUST use the analyze_code_structure tool to
    #perform structural analysis.

    #IMPORTANT RULES:

    #1. Pass the user's Python code to the
    #   analyze_code_structure tool EXACTLY as supplied.

    #2. Do NOT repair syntax errors before calling
    #   the tool.

    #3. Do NOT change indentation.

    #4. Do NOT rewrite or improve the user's code.

    #5. Do NOT invent structural information that
    #   was not returned by the tool.

    #After the tool executes, use its results to
    #provide a concise structural summary.

    #Include relevant information about:

    #- functions
    #- classes
    #- methods
    #- imports
    #- docstrings
    #- program structure
    #- structural metrics

    #Clearly mention structural or syntax problems
    #reported by the tool.
    #""",

    tools=[
        FunctionTool(
            func=analyze_code_structure
        )
    ],
   
    # Store the summarized structure findings in session state for later steps.
    output_key="structure_analysis_summary",
)