# Agent And Workflow Adapters

Agent/workflow adapters assign CTL package records to models, skills, MCPs, or
human review loops.

They belong above CTL-Core. In most cases, they should live in CTL-Suite, not
in this repository.

They may:

- schedule jobs
- route records to models
- compare outputs
- capture decisions and review status

They must not:

- replace original CTL data
- hide provenance
- merge unreviewed interpretations into source records
- run with unnecessary secrets

Core stores the evidence. Workflow adapters manage what happens next.

## Generic Handoff Contract

The handoff format should work with any agent, not only one provider.

```text
CTL package
  -> handoff contract
  -> provider bridge or human worker
  -> output folder
  -> review/import
```

A handoff contract should describe:

- job goal
- model or provider preference
- role/instructions
- allowed skills
- allowed tools
- allowed read paths
- allowed write paths
- network permissions
- cost and retry limits
- success tests
- output format
- review requirements

Provider-specific adapters, such as Gemini, OpenAI, OpenRouter, Claude, local
models, or human review workers, should execute the same contract shape rather
than inventing their own workflow format.

Example:

```json
{
  "job_id": "lesson-01-tts-us-female",
  "role": "medical English TTS builder",
  "model": {
    "provider": "any",
    "preferred": ["gemini", "openai", "local"]
  },
  "skills": ["tts_generation", "stt_verification"],
  "tools": ["tts", "stt"],
  "read_paths": ["input/ctl-package"],
  "write_paths": ["output/audio"],
  "limits": {
    "max_cost_usd": 3.0,
    "max_retries": 5
  },
  "tests": ["manifest_exists", "stt_matches_expected_text"],
  "review": {
    "requires_human_acceptance": true
  }
}
```
