# AGENTS.md

## Project Goal

This project is an agentic spreadsheet intelligence system for Excel workbooks. Its purpose is to preprocess workbooks, extract formulas and metadata, build dependency graphs, resolve spreadsheet references into business-readable variables, and answer questions with clear evidence.

The most important engineering principle is:

> Do not overcomplicate the system.

Keep code, logic, data structures, and workflows as simple as possible while preserving useful features, efficiency, performance, and correctness.

## Working Agreement

Agents must work in phases. Before starting any implementation phase:

1. Review the relevant project plan and current code.
2. Explain the intended implementation approach.
3. Provide a concise final plan for that phase.
4. Ask for user approval.
5. Build only after approval is given.

Do not begin coding a new phase just because the next step seems obvious. Approval is required before each phase.

## Planning Rules

Every phase plan should include:

- What will be built.
- Which files will be created or changed.
- What data structures or libraries will be used.
- What will intentionally be kept out of scope.
- How the result will be verified.

Prefer small, testable increments over large rewrites. If a task can be split into a simpler first version and later improvements, propose that split.

## Simplicity Guidelines

- Prefer straightforward Python modules and functions over complex frameworks.
- Use proven libraries for domain-specific work, such as `openpyxl` for Excel parsing and `networkx` for dependency graphs.
- Avoid premature abstractions, plugin systems, background workers, databases, or services unless the current phase clearly needs them.
- Keep data formats transparent and inspectable, such as JSON-compatible dictionaries and lists.
- Use clear names that match spreadsheet concepts: workbook, sheet, cell, range, formula, reference, dependency, lineage.
- Do not optimize before measuring or identifying a real bottleneck.
- Do not remove useful features in the name of simplicity.

## Evidence And Accuracy

Spreadsheet answers must be grounded in workbook evidence.

When implementing analysis or Q&A behavior:

- Preserve raw formulas, cell addresses, sheet names, values, named ranges, comments, merged cells, and formatting clues where relevant.
- Keep enough metadata to trace an answer back to source cells.
- Prefer deterministic preprocessing and tool calls over asking an LLM to infer workbook structure from scratch.
- Make uncertain mappings explicit instead of pretending they are exact.
- Do not hide ambiguity in business-variable resolution.

## Phase Discipline

Follow the project phases unless the user explicitly changes the order:

1. Workbook upload and preprocessing.
2. Formula extraction and reference parsing.
3. Dependency graph construction.
4. Formula variable resolution.
5. Metadata storage.
6. Natural-language query planning.
7. Tool execution and explanation generation.
8. Workbook comparison.

Each phase should produce a concrete deliverable before moving to the next phase.

## Implementation Standards

- Keep functions focused and easy to read.
- Add comments only when they clarify non-obvious logic.
- Keep public interfaces small.
- Validate inputs close to where they enter the system.
- Return structured results rather than formatted strings from core logic.
- Separate extraction, parsing, graph logic, and explanation logic.
- Avoid global mutable state unless there is a clear reason.
- Prefer deterministic tests with small fixture workbooks.

## Testing And Verification

For each approved phase, include practical verification:

- Unit tests for parsing and graph behavior where applicable.
- Small sample workbook fixtures for Excel-specific behavior.
- JSON output checks for preprocessing deliverables.
- Manual sanity checks for representative workbook cells and formulas.

If tests cannot be run, explain why and provide the closest available verification.

## Change Control

- Do not rewrite unrelated files.
- Do not introduce large dependencies without explaining why they are needed.
- Do not change the project scope without user approval.
- Do not silently skip requirements from `Project_plan.txt`.
- If the plan appears too complex, propose a simpler version before implementing.

## Communication Style

Be concise, specific, and practical.

Before implementation, say what you are about to build and why. After implementation, summarize what changed, how it was verified, and what the next approval gate is.

The default posture should be:

> Plan clearly, ask first, build simply, verify with evidence.
