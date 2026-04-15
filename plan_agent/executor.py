import io
import os
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pydantic import BaseModel

PERSISTENT_GLOBALS = {
    "__builtins__": __builtins__,
}

class CodeResponse(BaseModel):
    stdout: str
    stderr: str
    globals: dict = None


def reset_persistent_globals() -> None:
    keys_to_remove = [key for key in PERSISTENT_GLOBALS.keys() if key != "__builtins__"]
    for key in keys_to_remove:
        del PERSISTENT_GLOBALS[key]


def initialize_runtime_globals() -> None:
    PERSISTENT_GLOBALS["WORKSPACE_ROOT"] = os.getenv("PLAN_REPL_WORKSPACE_ROOT", "")

def execute_python(code: str):
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            workspace_root = PERSISTENT_GLOBALS.get("WORKSPACE_ROOT")
            previous_cwd = None
            if workspace_root:
                previous_cwd = os.getcwd()
                os.chdir(workspace_root)
            exec(code, PERSISTENT_GLOBALS)
            if previous_cwd is not None:
                os.chdir(previous_cwd)
        
        return CodeResponse(
            stdout=stdout_capture.getvalue(),
            stderr="",
            globals=PERSISTENT_GLOBALS,
        )
    except Exception as e:
        if 'previous_cwd' in locals() and previous_cwd is not None:
            os.chdir(previous_cwd)
        return CodeResponse(
            stdout=stdout_capture.getvalue(),
            stderr=traceback.format_exc(),
            globals=PERSISTENT_GLOBALS,
        )
