# Load modules at the AI gateway

Use this variant when developers already use your AI gateway and you cannot
change their machines. No additional skill, helper or MCP connection is needed
in the development tool.

The example supports LiteLLM's Anthropic Messages endpoint. It selects and loads
policy before each request. Other API formats are refused. The complete-injection
and client-loader variants remain available; choose one for each deployment.

## How it works

1. The gateway sends the core, module catalog and current task to the model in
   a separate selection request. Only the policy-selection tool is available.
2. The model returns module IDs. The gateway checks them and loads the approved
   texts, dependencies and blueprint values from its local policy package.
3. The gateway appends those rules to the original request. LiteLLM then handles
   the answer, including streaming and the client's ordinary tool calls.

The selection request stays inside the gateway. It cannot execute development
commands. Both model calls pass through LiteLLM's authentication, model access
checks and accounting with the caller's credentials.

This replaces the earlier proposal to hide tool rounds inside the answer.
LiteLLM's [agentic-loop hook](https://docs.litellm.ai/docs/proxy/agentic_loop_hook)
is documented as non-streaming only. Selecting policy first keeps normal
answers and streams on their existing path.

There is one extra model call per request, including token-count requests.
This adds latency and cost. LiteLLM accounts for both calls; the response sent
to the client reports the final call's usage. No conversation history is stored
by this adapter. Each request selects again from the context the client sends.

For the baseline alone, complete injection is simpler and avoids the extra
call. Use this selective variant when larger organization policies justify it;
measure total cost and latency before rollout. Less policy in the final request
does not necessarily mean fewer tokens across both calls.

## Set up LiteLLM

Use the reviewed checkout and an environment installed from
[`requirements-linux-py310.lock`](../../examples/organization-bundle/gateway/requirements-linux-py310.lock).
The lock is for Python 3.10 on Linux x86-64 and includes LiteLLM 1.101.0.
Install it with `python -m pip install --require-hashes -r PATH_TO_LOCK`.

Prepare a policy snapshot on the gateway machine:

```bash
python3 examples/organization-bundle/gateway/prepare.py --out /srv/aiscb/policy-release
```

For organization policy, add `--organization PATH` and
`--organization-sha256 TRUSTED_MANIFEST_DIGEST`. The command prints the snapshot
digest. Deliver the snapshot and that digest through your trusted release process.
The gateway checks the files at startup and keeps the verified texts in memory.

Set these values in the service configuration:

| Setting | Value |
| --- | --- |
| `CONFIG_FILE_PATH` | Your existing LiteLLM YAML configuration |
| `LITELLM_MASTER_KEY` | The existing secret used to protect LiteLLM; no default is supplied |
| `AISCB_POLICY_ROOT` | The prepared snapshot directory |
| `AISCB_POLICY_SHA256` | Its approved digest |

Keep the existing model definitions, provider credentials, user keys and access
rules. Do not enable the complete-injection callback on this deployment as well.
Run the wrapper using the same public gateway address and TLS frontend:

```bash
uvicorn --app-dir examples/organization-bundle/gateway managed:create_app \
  --factory --host 127.0.0.1 --port 4000 --limit-concurrency 64
```

The wrapper serves `/v1/messages` and `/v1/messages/count_tokens`. Keep LiteLLM's
administration routes on a separate protected service. The public frontend
must route these requests through the wrapper without an alternate unprotected
model route. It must terminate TLS; the example listens on loopback.

One deployment supplies the same policy release to all its authorized callers.
Use separate deployments for different organization policies. Keep the release
fixed while sessions are active; drain sessions before an update or rollback.
Policy files and the service configuration need organization-managed write access.

## Checks and limits

Run the fast checks with `make check`. Run the optional integration probe in the
locked environment:

```bash
python examples/organization-bundle/gateway/probe_litellm.py
```

The probe uses real LiteLLM and a local HTTP provider fixture. If Claude Code is
installed, it also tests an isolated CLI session. It uses no real provider key
and makes no paid model calls. It checks module delivery, dependency loading,
ordinary tool calls, streaming and rejection of invalid credentials.

On 2026-09-19 these checks passed with LiteLLM 1.101.0 and Claude Code 2.1.278
on Linux. The 110 locked wheels were checked against PyPI hashes and its
version-specific vulnerability reports; none were reported at that time.
Repeat the integration and dependency checks before changing the locked versions.

The adapter refuses unknown module IDs, changed policy files at startup,
unsupported request fields and failed selection. Request sizes and execution
time are bounded. A disconnect cancels outstanding work. The gateway does not
see files that the client has not supplied, and model selection can still miss
a relevant rule. Test selection with your real models and typical tasks before
rollout; the fixture does not prove that behavior or support for other clients.
