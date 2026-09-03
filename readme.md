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
- `run.log` - live, neutral progress events safe to use for behavior diagnosis

The run ID and paths are printed before the first model request. While a model
request is pending, the console and `run.log` receive a heartbeat every 30
seconds. The neutral log records timings, stages, retries, counts, status codes,
and error types. When the endpoint returns standard token usage, it also records
per-call prompt/completion/total token counts and end-to-end output tokens per
second. It does not record the task, prompts, file contents, model responses,
endpoint, model name, or credentials.

The Python execution loop starts in `workspace/` and is instructed to work
there. It is an automation runtime, not an operating-system security sandbox;
run it only with the OS permissions and data access appropriate for the task.

## Configuration

Setup creates an ignored plain-text file named `llm_config.txt` from
`llm_config.example.txt`. Edit that one file before running the agent. At
minimum configure:

- `LLM_BASE_URL` - full Chat Completions request URL
- `LLM_API_KEY` - API credential when authentication is enabled
- `LLM_MODEL` - model identifier used for planning and execution

The configuration file is authoritative: inherited `LLM_*` environment
variables are cleared before it is loaded. The transport supports hosted
gateways, custom gateways, and unauthenticated local servers without
provider-specific source changes:

- `LLM_AUTH_HEADER` and `LLM_AUTH_PREFIX` control authentication
- `LLM_CHOICES_PATH` locates the response choices array
- `LLM_USAGE_PATH` locates the optional standard token-usage object
- `LLM_EXTRA_BODY_JSON` adds model or gateway options
- `LLM_MAX_TOKENS_FIELD` selects the gateway's completion-limit field name
- `LLM_VERIFY_TLS` controls certificate verification
- `LLM_STRUCTURED_OUTPUT` supports `json_schema`, `json_object`, and
  `prompt_only` for gateways with different structured-output capabilities

The real `llm_config.txt` is ignored by Git. Never commit it. Use `<none>` as
`LLM_AUTH_HEADER` for an unauthenticated local endpoint, or as
`LLM_AUTH_PREFIX` when a gateway expects the raw key value. Set
`LLM_CHOICES_PATH` when a gateway wraps the standard choices array. Put any
optional request fields in `LLM_EXTRA_BODY_JSON`. Set `LLM_USAGE_PATH` to the
corresponding wrapped usage object, or to `<none>` when usage is unavailable.

Reasoning files are written only when an endpoint returns a non-empty
`reasoning` or `reasoning_content` field. An empty or absent field cannot be
reconstructed by the agent. Because requests are non-streaming for broad
gateway compatibility, the runtime can measure full request duration and
end-to-end output rate, but not time to first token.

## Linux Setup

```bash
./setup_venv.sh
# Edit llm_config.txt in a text editor.
.venv/bin/python llm_preflight.py
.venv/bin/python plan_repl_agent.py "Create a text file containing ten words"
```

## Windows PowerShell Setup

From the cloned repository:

```powershell
.\setup_windows.ps1 -Python "C:\Program Files\Python313\python.exe"
# Edit llm_config.txt in a text editor.
.\.venv\Scripts\python.exe .\llm_preflight.py
.\.venv\Scripts\python.exe .\plan_repl_agent.py `
  "Create a text file containing ten words"
```

The setup script finds the `uv` executable on `PATH` or in the current user's
Python AppData directories. If needed, pass its exact path with
`-UvPath "C:\path\to\uv.exe"`.

To use another configuration file on either operating system, pass
`--config path/to/file.txt` to both commands. The repository intentionally
contains no real endpoint, model, header, or credential values.

## Main Files

- `plan_repl_agent.py` - single-run entrypoint
- `plan_agent/run_agent.py` - plan/step/replan loop
- `plan_agent/run_step.py` - per-step model loop
- `plan_agent/executor.py` - persistent Python execution environment
- `plan_agent/utils.py` - provider-neutral HTTP transport
- `plan_agent/config.py` - strict plain-text configuration loader
- `llm_preflight.py` - minimal structured-output check

`runs/`, `llm_config.txt`, `.env`, virtual environments, and bytecode are
ignored by Git.
