# VAHA Project Instructions

VAHA Stands for Varabaiba's Handy tools. This is a collection for small tools. So every tool is located in its own sub-folder of the project.

## Instruction Scope

* Treat this file as the primary source of project-specific working rules.
* Before creating or modifying Python code, read and apply `.agents/PYTHON.md`.
* `.agents/PYTHON.md` defines mandatory Python naming, coding, documentation, testing, and source-structure conventions for this repository.
* Do not replace conventions defined in `.agents/PYTHON.md` with generic PEP recommendations where they differ.
* If a more specific `AGENTS.md` exists in a subdirectory, apply the more local file for work in that area.
* Explicit instructions from the user for the current task take precedence over repository guidance.

## Project Principles

* Preserve the existing project architecture and established patterns unless the task requires changing them.
* Keep data collection, application logic, persistence, and Streamlit presentation responsibilities separated where the existing architecture provides such separation.
* Do not move application logic into Streamlit UI code merely for convenience.
* Reuse existing project services, helpers, models, and abstractions before introducing new ones.
* Prefer clear and maintainable implementations over unnecessarily complex solutions.
* Avoid introducing new dependencies when the Python standard library or an existing project dependency reasonably solves the problem.

