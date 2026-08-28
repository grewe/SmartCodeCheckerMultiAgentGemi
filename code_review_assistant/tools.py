"""
Tools for the Code Review Assistant.

These tools provide safe code analysis, style checking, test generation,
and feedback management capabilities using ADK's built-in code executor.
"""

import ast
import asyncio
import hashlib
import json
import os
import pycodestyle
import tempfile
import logging
from datetime import datetime
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from google.genai import types
from google.adk.tools import ToolContext
from .constants import StateKeys





# Configure logging
logger = logging.getLogger(__name__)


async def analyze_code_structure(code: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Analyzes Python code structure using AST parsing.

    This tool parses Python code to extract structural information
    including functions, classes, imports, and complexity metrics.

    Args:
        code: Python source code to analyze
        tool_context: ADK tool context for state management

    Returns:
        Dictionary containing analysis results and status
    """
    logger.info("Tool: Analyzing code structure...")

    try:
        # Validate input
        if not code or not isinstance(code, str):
            return {
                "status": "error",
                "message": "No code provided or invalid input"
            }

        # MODULE_4_STEP_3_ADD_ASYNC
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor() as executor:
        	tree = await loop.run_in_executor(
			executor,
        		ast.parse,
        		code
    	 	)

            # MODULE_4_STEP_4_EXTRACT_DETAILS
        	analysis = await loop.run_in_executor(
    			executor,
   			 _extract_code_structure,
   			 tree,
   			 code
		)

        # MODULE_4_STEP_2_ADD_STATE_STORAGE
        tool_context.state[StateKeys.CODE_TO_REVIEW] = code
        tool_context.state[StateKeys.CODE_ANALYSIS] = analysis
        tool_context.state[StateKeys.CODE_LINE_COUNT] = len(code.splitlines())

        logger.info(f"Tool: Analysis complete - {analysis['metrics']['function_count']} functions, "
                    f"{analysis['metrics']['class_count']} classes")

        return {
            "status": "success",
            "analysis": analysis,
            "summary": f"Found {analysis['metrics']['function_count']} functions and "
                       f"{analysis['metrics']['class_count']} classes"
        }

    except SyntaxError as e:
        error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
        logger.error(f"Tool: {error_msg}")
        tool_context.state[StateKeys.CODE_TO_REVIEW] = code
        tool_context.state[StateKeys.SYNTAX_ERROR] = error_msg

        return {
            "status": "error",
            "error_type": "syntax",
            "message": error_msg,
            "line": e.lineno,
            "offset": e.offset
        }
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.error(f"Tool: {error_msg}", exc_info=True)

        return {
            "status": "error",
            "error_type": "parse",
            "message": error_msg
        }


# MODULE_4_STEP_4_HELPER_FUNCTION
def _extract_code_structure(tree: ast.AST, code: str) -> dict[str, Any]:
    """
    Extract detailed structural information from a Python AST.

    Args:
        tree: Parsed Python abstract syntax tree.
        code: Original Python source code.

    Returns:
        Dictionary containing structural information about the program.
    """

    functions = []
    classes = []
    imports = []
    docstrings = []

    # Walk through every node in the AST.
    for node in ast.walk(tree):

        # ---------------------------------------------------------
        # FUNCTIONS
        # ---------------------------------------------------------

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

            function_info = {
                "name": node.name,
                "line_number": node.lineno,
                "arguments": [
                    arg.arg for arg in node.args.args
                ],
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "docstring": ast.get_docstring(node),
                "decorators": [
                    ast.unparse(decorator)
                    for decorator in node.decorator_list
                ],
            }

            functions.append(function_info)

        # ---------------------------------------------------------
        # CLASSES
        # ---------------------------------------------------------

        elif isinstance(node, ast.ClassDef):

            class_info = {
                "name": node.name,
                "line_number": node.lineno,

                "methods": [
                    item.name
                    for item in node.body
                    if isinstance(
                        item,
                        (ast.FunctionDef, ast.AsyncFunctionDef)
                    )
                ],

                "docstring": ast.get_docstring(node),

                "base_classes": [
                    ast.unparse(base)
                    for base in node.bases
                ],
            }

            classes.append(class_info)

        # ---------------------------------------------------------
        # IMPORT statements
        #
        # Example:
        #     import math
        #     import os
        # ---------------------------------------------------------

        elif isinstance(node, ast.Import):

            for alias in node.names:

                imports.append({
                    "module": alias.name,
                    "alias": alias.asname,
                    "type": "import",
                    "line_number": node.lineno,
                })

        # ---------------------------------------------------------
        # FROM ... IMPORT statements
        #
        # Example:
        #     from pathlib import Path
        # ---------------------------------------------------------

        elif isinstance(node, ast.ImportFrom):

            for alias in node.names:

                imports.append({
                    "module": node.module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "type": "from_import",
                    "line_number": node.lineno,
                })

    # -------------------------------------------------------------
    # DOCUMENTATION
    # -------------------------------------------------------------

    module_docstring = ast.get_docstring(tree)

    if module_docstring:

        docstrings.append({
            "type": "module",
            "text": module_docstring,
        })

    for function in functions:

        if function["docstring"]:

            docstrings.append({
                "type": "function",
                "name": function["name"],
                "text": function["docstring"],
            })

    for class_info in classes:

        if class_info["docstring"]:

            docstrings.append({
                "type": "class",
                "name": class_info["name"],
                "text": class_info["docstring"],
            })

    # -------------------------------------------------------------
    # PROGRAM METRICS
    # -------------------------------------------------------------

    lines = code.splitlines()

    function_lengths = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):

            if hasattr(node, "end_lineno") and node.end_lineno:

                function_length = (
                    node.end_lineno - node.lineno + 1
                )

                function_lengths.append(function_length)

    if function_lengths:

        average_function_length = (
            sum(function_lengths) / len(function_lengths)
        )

    else:

        average_function_length = 0

    # Check whether the program defines main().
    has_main_function = any(
        function["name"] == "main"
        for function in functions
    )

    # Check whether the program contains:
    #
    # if __name__ == "__main__":
    #
    has_main_guard = False

    for node in ast.walk(tree):

        if isinstance(node, ast.If):

            try:

                condition = ast.unparse(node.test)

                if (
                    "__name__" in condition
                    and "__main__" in condition
                ):

                    has_main_guard = True

            except Exception:

                pass

    # -------------------------------------------------------------
    # FINAL STRUCTURED RESULT
    # -------------------------------------------------------------

    return {
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "docstrings": docstrings,

        "metrics": {
            "line_count": len(lines),
            "function_count": len(functions),
            "class_count": len(classes),
            "import_count": len(imports),
            "has_main_function": has_main_function,
            "has_main_guard": has_main_guard,
            "average_function_length": average_function_length,
        },
    }



def _calculate_avg_function_length(
	tree: ast.AST
) -> float:
   
	 """Calculate average function length in lines."""

	 function_lengths = []
	
	 for node in ast.walk(tree):

     	   if isinstance(node, ast.FunctionDef):

      	      if (
       	         hasattr(node, "end_lineno")
       	         and hasattr(node, "lineno")
        	):

                	length = (
                    		node.end_lineno
                    		- node.lineno
                    		+ 1
                	)

                	function_lengths.append(length)

	 if function_lengths:

     		return (
       			sum(function_lengths)
        		/ len(function_lengths)
        	)

	 return 0.0

# MODULE_5_STEP_1_STYLE_CHECKER_TOOL
async def check_code_style(
    code: str,
    tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Checks code style compliance using pycodestyle (PEP 8).

    Args:
        code: Python source code to check
              (or retrieve from shared state)
        tool_context: ADK tool context

    Returns:
        Dictionary containing style score and issues
    """

    logger.info("Tool: Checking code style...")

    try:

        # Retrieve code from shared state if the
        # caller did not explicitly provide code.
        if not code:

            code = tool_context.state.get(
                StateKeys.CODE_TO_REVIEW,
                ""
            )

            if not code:

                return {
                    "status": "error",
                    "message":
                        "No code provided or found in state"
                }

        # Run the synchronous style checker in
        # a worker thread so it does not block
        # ADK's asynchronous event loop.
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor() as executor:

            result = await loop.run_in_executor(
                executor,
                _perform_style_check,
                code
            )

        # Store results so later agents can use them.
        tool_context.state[
            StateKeys.STYLE_SCORE
        ] = result["score"]

        tool_context.state[
            StateKeys.STYLE_ISSUES
        ] = result["issues"]

        tool_context.state[
            StateKeys.STYLE_ISSUE_COUNT
        ] = result["issue_count"]

        logger.info(
            f"Tool: Style check complete - "
            f"Score: {result['score']}/100, "
            f"Issues: {result['issue_count']}"
        )

        return result

    except Exception as e:

        error_msg = (
            f"Style check failed: {str(e)}"
        )

        logger.error(
            f"Tool: {error_msg}",
            exc_info=True
        )

        # Put safe defaults into state.
        tool_context.state[
            StateKeys.STYLE_SCORE
        ] = 0

        tool_context.state[
            StateKeys.STYLE_ISSUES
        ] = []

        return {
            "status": "error",
            "message": error_msg,
            "score": 0
        }

# MODULE_5_STEP_1_STYLE_HELPERS
def _perform_style_check(
    code: str
) -> Dict[str, Any]:

    import io
    import sys

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False
    ) as tmp:

        tmp.write(code)
        tmp_path = tmp.name

    try:

        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        style_guide = pycodestyle.StyleGuide(
            quiet=False,
            max_line_length=100,
            ignore=["E501", "W503"]
        )

        style_guide.check_files([tmp_path])

        sys.stdout = old_stdout

        output = captured_output.getvalue()

        issues = []

        for line in output.strip().split("\n"):

            if line and ":" in line:

                parts = line.split(":", 4)

                if len(parts) >= 4:

                    try:
                        issues.append({
                            "line": int(parts[1]),
                            "column": int(parts[2]),
                            "code":
                                parts[3].split()[0],
                            "message":
                                parts[3].strip()
                        })

                    except (
                        ValueError,
                        IndexError
                    ):
                        pass

        try:

            tree = ast.parse(code)

            naming_issues = (
                _check_naming_conventions(tree)
            )

            issues.extend(naming_issues)

        except SyntaxError:
            pass

        score = _calculate_style_score(
            issues
        )

        return {
            "status": "success",
            "score": score,
            "issue_count": len(issues),
            "issues": issues[:10],
            "summary":
                f"Style score: {score}/100 "
                f"with {len(issues)} violations"
        }

    finally:

        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _check_naming_conventions(
    tree: ast.AST
) -> List[Dict[str, Any]]:

    naming_issues = []

    for node in ast.walk(tree):

        if isinstance(node, ast.FunctionDef):

            if (
                not node.name.startswith("_")
                and node.name != node.name.lower()
            ):

                naming_issues.append({
                    "line": node.lineno,
                    "column": node.col_offset,
                    "code": "N802",
                    "message":
                        f"N802 function name "
                        f"'{node.name}' "
                        f"should be lowercase"
                })

        elif isinstance(node, ast.ClassDef):

            if (
                not node.name[0].isupper()
                or "_" in node.name
            ):

                naming_issues.append({
                    "line": node.lineno,
                    "column": node.col_offset,
                    "code": "N801",
                    "message":
                        f"N801 class name "
                        f"'{node.name}' should use "
                        f"CapWords convention"
                })

    return naming_issues

def _calculate_style_score(
    issues: List[Dict[str, Any]]
) -> int:

    if not issues:
        return 100

    weights = {
        "E1": 10,
        "E2": 3,
        "E3": 5,
        "E4": 8,
        "E5": 5,
        "E7": 7,
        "E9": 10,
        "W2": 2,
        "W3": 2,
        "W5": 3,
        "N8": 7,
    }

    total_deduction = 0

    for issue in issues:

        code_prefix = (
            issue["code"][:2]
            if len(issue["code"]) >= 2
            else "E2"
        )

        weight = weights.get(
            code_prefix,
            3
        )

        total_deduction += weight

    return max(
        0,
        100 - min(total_deduction, 100)
    )

# MODULE_5_STEP_4_SEARCH_PAST_FEEDBACK
async def search_past_feedback(
    developer_id: str,
    tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Search for past feedback in memory service.
    """

    logger.info(
        f"Tool: Searching for past feedback "
        f"for developer {developer_id}..."
    )

    try:

        if not developer_id:
            developer_id = tool_context.state.get(
                StateKeys.USER_ID,
                "default_user"
            )

        if hasattr(tool_context, "search_memory"):

            try:

                queries = [
                    f"developer:{developer_id} code review feedback",
                    f"developer:{developer_id} common issues",
                    f"developer:{developer_id} improvements"
                ]

                all_feedback = []

                patterns = {
                    "common_issues": [],
                    "improvements": [],
                    "strengths": []
                }

                for query in queries:

                    search_result = await tool_context.search_memory(
                        query
                    )

                    if (
                        search_result
                        and hasattr(search_result, "memories")
                    ):

                        for memory in search_result.memories[:5]:

                            memory_text = (
                                memory.text
                                if hasattr(memory, "text")
                                else str(memory)
                            )

                            all_feedback.append(memory_text)

                            if "style" in memory_text.lower():
                                patterns[
                                    "common_issues"
                                ].append(
                                    "style compliance"
                                )

                            if "improved" in memory_text.lower():
                                patterns[
                                    "improvements"
                                ].append(
                                    "showing improvement"
                                )

                            if "excellent" in memory_text.lower():
                                patterns[
                                    "strengths"
                                ].append(
                                    "consistent quality"
                                )

                tool_context.state[
                    StateKeys.PAST_FEEDBACK
                ] = all_feedback

                tool_context.state[
                    StateKeys.FEEDBACK_PATTERNS
                ] = patterns

                return {
                    "status": "success",
                    "feedback_found": True,
                    "count": len(all_feedback),
                    "summary":
                        " | ".join(all_feedback[:3])
                        if all_feedback
                        else "No feedback",
                    "patterns": patterns
                }

            except Exception as e:
                logger.warning(
                    f"Tool: Memory search error: {e}"
                )

        cached_feedback = tool_context.state.get(
            StateKeys.USER_PAST_FEEDBACK_CACHE,
            []
        )

        if cached_feedback:

            tool_context.state[
                StateKeys.PAST_FEEDBACK
            ] = cached_feedback

            return {
                "status": "success",
                "feedback_found": True,
                "count": len(cached_feedback),
                "summary": "Using cached feedback",
                "patterns": {}
            }

        tool_context.state[
            StateKeys.PAST_FEEDBACK
        ] = []

        logger.info(
            "Tool: No past feedback found"
        )

        return {
            "status": "success",
            "feedback_found": False,
            "message":
                "No past feedback available - "
                "this appears to be a first submission",
            "patterns": {}
        }

    except Exception as e:

        error_msg = (
            f"Feedback search error: {str(e)}"
        )

        logger.error(
            f"Tool: {error_msg}",
            exc_info=True
        )

        tool_context.state[
            StateKeys.PAST_FEEDBACK
        ] = []

        return {
            "status": "error",
            "message": error_msg,
            "feedback_found": False
        }

# MODULE_5_STEP_4_UPDATE_GRADING_PROGRESS
async def update_grading_progress(
    tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Updates grading progress counters and metrics in state.
    """

    logger.info(
        "Tool: Updating grading progress..."
    )

    try:

        current_time = datetime.now().isoformat()

        state_updates = {}

        state_updates[
            StateKeys.TEMP_PROCESSING_TIMESTAMP
        ] = current_time

        attempts = tool_context.state.get(
            StateKeys.GRADING_ATTEMPTS,
            0
        ) + 1

        state_updates[
            StateKeys.GRADING_ATTEMPTS
        ] = attempts

        state_updates[
            StateKeys.LAST_GRADING_TIME
        ] = current_time

        lifetime_submissions = (
            tool_context.state.get(
                StateKeys.USER_TOTAL_SUBMISSIONS,
                0
            ) + 1
        )

        state_updates[
            StateKeys.USER_TOTAL_SUBMISSIONS
        ] = lifetime_submissions

        state_updates[
            StateKeys.USER_LAST_SUBMISSION_TIME
        ] = current_time

        current_style_score = tool_context.state.get(
            StateKeys.STYLE_SCORE,
            0
        )

        last_style_score = tool_context.state.get(
            StateKeys.USER_LAST_STYLE_SCORE,
            0
        )

        score_improvement = (
            current_style_score
            - last_style_score
        )

        state_updates[
            StateKeys.USER_LAST_STYLE_SCORE
        ] = current_style_score

        state_updates[
            StateKeys.SCORE_IMPROVEMENT
        ] = score_improvement

        test_results = tool_context.state.get(
            StateKeys.TEST_EXECUTION_SUMMARY,
            {}
        )

        if isinstance(test_results, str):

            try:
                test_results = json.loads(
                    test_results
                )
            except:
                test_results = {}

        if (
            test_results
            and test_results
                .get("test_summary", {})
                .get("total_tests_run", 0) > 0
        ):

            summary = test_results["test_summary"]

            total = summary.get(
                "total_tests_run",
                0
            )

            passed = summary.get(
                "tests_passed",
                0
            )

            if total > 0:

                pass_rate = (
                    passed / total
                ) * 100

                state_updates[
                    StateKeys.USER_LAST_TEST_PASS_RATE
                ] = pass_rate

        for key, value in state_updates.items():
            tool_context.state[key] = value

        logger.info(
            f"Tool: Progress updated - "
            f"Attempt #{attempts}, "
            f"Lifetime: {lifetime_submissions}"
        )

        return {
            "status": "success",
            "session_attempts": attempts,
            "lifetime_submissions":
                lifetime_submissions,
            "timestamp": current_time,
            "improvement": {
                "style_score_change":
                    score_improvement,
                "direction":
                    "improved"
                    if score_improvement > 0
                    else "declined"
            },
            "summary":
                f"Attempt #{attempts} recorded, "
                f"{lifetime_submissions} "
                f"total submissions"
        }

    except Exception as e:

        error_msg = (
            f"Progress update error: {str(e)}"
        )

        logger.error(
            f"Tool: {error_msg}",
            exc_info=True
        )

        return {
            "status": "error",
            "message": error_msg
        }

# MODULE_5_STEP_4_SAVE_GRADING_REPORT
async def save_grading_report(
    feedback_text: str,
    tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Saves a detailed grading report.
    """

    logger.info(
        "Tool: Saving grading report..."
    )

    try:

        code = tool_context.state.get(
            StateKeys.CODE_TO_REVIEW,
            ""
        )

        analysis = tool_context.state.get(
            StateKeys.CODE_ANALYSIS,
            {}
        )

        style_score = tool_context.state.get(
            StateKeys.STYLE_SCORE,
            0
        )

        style_issues = tool_context.state.get(
            StateKeys.STYLE_ISSUES,
            []
        )

        test_results = tool_context.state.get(
            StateKeys.TEST_EXECUTION_SUMMARY,
            {}
        )

        if isinstance(test_results, str):

            try:
                test_results = json.loads(
                    test_results
                )
            except:
                test_results = {}

        timestamp = datetime.now().isoformat()

        report = {
            "timestamp": timestamp,

            "grading_attempt":
                tool_context.state.get(
                    StateKeys.GRADING_ATTEMPTS,
                    1
                ),

            "code": {
                "content": code,
                "line_count":
                    len(code.splitlines()),
                "hash":
                    hashlib.md5(
                        code.encode()
                    ).hexdigest()
            },

            "analysis": analysis,

            "style": {
                "score": style_score,
                "issues": style_issues[:5]
            },

            "tests": test_results,

            "feedback": feedback_text,

            "improvements": {
                "score_change":
                    tool_context.state.get(
                        StateKeys.SCORE_IMPROVEMENT,
                        0
                    ),

                "from_last_score":
                    tool_context.state.get(
                        StateKeys.USER_LAST_STYLE_SCORE,
                        0
                    )
            }
        }

        report_json = json.dumps(
            report,
            indent=2
        )

        report_part = types.Part.from_text(
            text=report_json
        )

        if hasattr(
            tool_context,
            "save_artifact"
        ):

            try:

                filename = (
                    "grading_report_"
                    f"{timestamp.replace(':', '-')}"
                    ".json"
                )

                version = await (
                    tool_context.save_artifact(
                        filename,
                        report_part
                    )
                )

                await tool_context.save_artifact(
                    "latest_grading_report.json",
                    report_part
                )

                tool_context.state[
                    StateKeys.USER_LAST_GRADING_REPORT
                ] = report

                return {
                    "status": "success",
                    "artifact_saved": True,
                    "filename": filename,
                    "version": str(version),
                    "size": len(report_json),
                    "summary":
                        f"Report saved as {filename}"
                }

            except Exception as artifact_error:

                logger.warning(
                    "Artifact service error: "
                    f"{artifact_error}, "
                    "falling back to state storage"
                )

        tool_context.state[
            StateKeys.USER_LAST_GRADING_REPORT
        ] = report

        logger.info(
            "Tool: Report saved to state "
            "(artifact service not available)"
        )

        return {
            "status": "success",
            "artifact_saved": False,
            "message":
                "Report saved to state only",
            "size": len(report_json),
            "summary":
                "Report saved to session state"
        }

    except Exception as e:

        error_msg = (
            f"Report save error: {str(e)}"
        )

        logger.error(
            f"Tool: {error_msg}",
            exc_info=True
        )

        try:

            tool_context.state[
                StateKeys.USER_LAST_GRADING_REPORT
            ] = {
                "error": error_msg,
                "feedback": feedback_text,
                "timestamp":
                    datetime.now().isoformat()
            }

        except:
            pass

        return {
            "status": "error",
            "message": error_msg,
            "artifact_saved": False,
            "summary":
                f"Failed to save report: "
                f"{error_msg}"
        }

# MODULE_6_STEP_3_VALIDATE_FIXED_STYLE


# MODULE_6_STEP_3_COMPILE_FIX_REPORT


# MODULE_6_STEP_3_EXIT_FIX_LOOP


# MODULE_6_STEP_6_SAVE_FIX_REPORT


# Module exports
__all__ = [
    'analyze_code_structure',
    'check_code_style',
    'search_past_feedback',
    'update_grading_progress',
    'save_grading_report',
    'validate_fixed_style',
    'compile_fix_report',
    'save_fix_report',
]