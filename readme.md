# plan_repl_agent

General-purpose planning and execution agent for local file workspaces.

The `general_purpose` branch contains only reusable agent logic. It does not
contain provider, organization, machine, or task-specific configuration.

## How It Works

1. A planning call creates a short structured plan.
2. The executor completes one bounded step at a time with Python.
3. After each step, a structured decision continues, replans, completes, or
   aborts the task.
4. A final structured call prepares the user-facing response.

Every run gets a fresh directory under `runs/<run_id>/`:

- `workspace/` - files created for the task
- `step_logs/` - plan, decisions, model messages, and execution output
- `task.txt` - original task
- `result.json` - structured final result
- `final_answer.txt` - final user-facing answer

The Python execution loop starts in `workspace/` and is instructed to work
there. It is an automation runtime, not an operating-system security sandbox;
run it only with the OS permissions and data access appropriate for the task.

## Configuration

Copy `.env.sample` to `.env`, or set the same variables in the current shell.
At minimum configure:

- `LLM_BASE_URL` - full Chat Completions request URL
- `LLM_API_KEY` - API credential
- `LLM_MODEL` - model identifier used for planning and execution

The transport is configurable without provider-specific source changes:

- `LLM_AUTH_HEADER` and `LLM_AUTH_PREFIX` control authentication
- `LLM_CHOICES_PATH` locates the response choices array
- `LLM_EXTRA_BODY_JSON` adds model or gateway options
- `LLM_MAX_TOKENS_FIELD` selects the gateway's completion-limit field name
- `LLM_VERIFY_TLS` controls certificate verification
- `LLM_STRUCTURED_OUTPUT=json_schema` uses structured output; set
  `prompt_only` only when a gateway does not implement it

Secrets belong only in environment variables or an untracked local `.env`.
Use `<none>` as `LLM_AUTH_HEADER` for an unauthenticated local endpoint, or as
`LLM_AUTH_PREFIX` when a gateway expects the raw key value.

## Linux Setup

```bash
./setup_venv.sh
.venv/bin/python llm_preflight.py
.venv/bin/python plan_repl_agent.py "Create a text file containing ten words"
```

## Windows PowerShell Setup

From the cloned repository:

```powershell
.\setup_windows.ps1 -Python "C:\Program Files\Python313\python.exe"
.\.venv\Scripts\python.exe .\llm_preflight.py
.\.venv\Scripts\python.exe .\plan_repl_agent.py `
  "Create a text file containing ten words"
```

Set the `LLM_*` variables in the same PowerShell process before the preflight.
The repository intentionally does not include any real endpoint, model, header,
or credential values.

## Main Files

- `plan_repl_agent.py` - single-run entrypoint
- `plan_agent/run_agent.py` - plan/step/replan loop
- `plan_agent/run_step.py` - per-step model loop
- `plan_agent/executor.py` - persistent Python execution environment
- `plan_agent/utils.py` - provider-neutral HTTP transport
- `llm_preflight.py` - minimal structured-output check

`runs/`, `.env`, virtual environments, and bytecode are ignored by Git.
