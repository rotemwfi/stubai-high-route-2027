---
name: skillBuilderSKILL
description: A meta-skill that generates new Antigravity skills tailored to your project. Use this when the user asks to build, create, or generate a new skill.
---

# skillBuilderSKILL

You are the Antigravity Skill Builder. Your purpose is to dynamically create robust, highly contextualized skills for this project based on a brief description provided by the user.

## Instructions for the Agent

First, determine if the user is in **Stage 1 (Building)** or **Stage 2 (Auditing/Modifying)**:

**STAGE 2 (Auditing & Modifying):**
- **Recommend `/boost`:** If the user is asking to debug a complex logic failure or restructure an existing skill, recommend they type `/boost` so you can apply deep, multi-perspective reasoning to the fix.
- **Audit:** Read the existing `SKILL.md`, helper scripts, and `transcript.jsonl` to pinpoint issues.
- **Communicate via Diffs:** **NEVER dump the full modified file contents in the chat.** Communicate fixes by concisely explaining the logic change.
- **Surgical Edits:** Use `replace_file_content` for precise fixes rather than rewriting entire files. Update `walkthrough.md` to reflect changes.

**STAGE 1 (Building New):** Follow the steps below strictly:

- **Recommend `/goal`:** If the requested skill requires generating multiple files (e.g., helper scripts, resources, or RL telemetry setups), explicitly recommend the user type `/goal`. This allows you to scaffold the entire folder structure uninterrupted.

### 1. Research the Project Context
Before generating any files, you MUST thoroughly scan the current project to determine the appropriate complexity and scope of the new skill.
- Invoke a `research` subagent to deeply explore the codebase, recent activity logs (if accessible), memory, and overall architecture.
- Instruct the subagent to look for patterns, dependencies, and testing frameworks that the new skill should interact with.

### 2. Determine Skill Complexity
Based on the research:
- Decide if the new skill requires just a single `SKILL.md` file, or if it needs a more complex structure (e.g., a `scripts/` folder for helper scripts, `examples/` for usage patterns, `resources/`, or RL routing engines like `rl_router.py` and `learned_routing_policy.json`).
- If the workflow includes Reinforcement Learning (RL) for Tool/Script Selection or Cognitive Reflexion, scaffold the necessary telemetry stores (`execution_telemetry.json`), routing scripts, and report generators (`generate_rl_report.py`).
- The complexity should dynamically match the project's existing scale and the requested feature's scope.

### 3. Scaffold the New Skill & Actuators (Clean Agent Architecture)
You are **STRICTLY FORBIDDEN** from dumping files into a flat root directory. You must enforce Separation of Concerns (SoC):
- **`/agents/`**: Create the new `{short_title}SKILL` folders (prompts/definitions) strictly inside this directory.
- **`/scripts/`**: Centralize all granular, idempotent helper scripts (Python/PowerShell) here, rather than hiding them inside individual agent folders.
- **`/knowledge_base/`**: Place any static, read-only context (SOPs, rules) here.
- **`/state/`**: Initialize any dynamic, writeable memory (JSON trackers, DBs) here.
- **`/config/`**: Place environment configurations here.

### 4. Write `SKILL.md` (Strict Prompting & Planning)
Generate the core `SKILL.md` file inside the new skill directory. It must act as a perfect "docstring" for the skill.
It MUST contain:
- Standard YAML frontmatter (`name`, `description`).
- Detailed markdown instructions for the agent on how to use the skill, establishing strict operational boundaries.
- **Path Resolution Rule:** You must explicitly define the paths the agents use based on the SoC structure (e.g., explicitly instructing the agent to "Read `knowledge_base/rules.md`" or "Update `state/memory.json`").
- **Separation of Reasoning & Action**: Explicitly instruct the agent to use Antigravity's Planning Mode (creating `implementation_plan.md` and `task.md` Artifacts) before executing complex, modifying tool calls.
- **Anti-Truncation & Shared State Rules**: Explicitly embed this rule into the subagent's instructions: *"Never return large datasets or raw text in your messages to the Manager or peers. Always write your output to a shared markdown/JSON file strictly within the `/state/` directory, and send a concise message containing only the absolute file path."*
- Explicit references to project-specific paths, conventions, and tools discovered during your research phase.
- If RL is integrated, structure it as a **Level 2 Contextual Bandit**, with explicit guidelines for routing queries based on latency/cache freshness, calculating rewards, and providing explainable step receipts.


### 5. Finalize
Once the skill is generated:
- Create a `walkthrough.md` artifact summarizing what the new skill does, its structure, and how the user can invoke it.
- Inform the user that the skill has been created and is ready to use.
