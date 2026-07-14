# Prompting Guidelines for Grok

When asking questions or giving instructions in this project, include one of the following at the start of your prompt to help maintain consistency:

- "Check PROJECT_NOTES.md before answering..."
- "Recall our branching strategy and directory structure from PROJECT_NOTES.md..."
- "Using the decisions documented in PROJECT_NOTES.md..."
- "We previously decided X according to PROJECT_NOTES.md..."

This helps reduce repetition of already-covered topics.

---

# ocp-airgap Project Notes

This file serves as the single source of truth for important decisions, conventions, and context for this project.

---

## Branching Strategy

- `main` — Stable / production-ready code only
- `dev` — Main development and integration branch
- `feature/*` — All new work happens on feature branches created from `dev`
  - Example: `feature/hw-interrogator`, `feature/improve-disk-detection`
- Never work directly on `main` or `dev` for new changes

**Rule:** Always create feature branches from the latest `dev`.

---

## Directory Structure

~/ansible/
├── ipa-elements/
│   └── hw-discovery/          # Custom DIB element for hardware discovery
├── roles/
│   ├── hw_collector/          # Flask/Gunicorn collector role
│   └── hw_discovery/          # (Legacy or supporting role)
├── playbooks/
├── environments/
│   └── dev/
├── docs/
├── PROJECT_NOTES.md
├── .gitignore
└── .gitattributes

cat > PROJECT_NOTES.md << 'EOF'
# ocp-airgap Project Notes

This file serves as the single source of truth for important decisions, conventions, and context for this project.

---

## Branching Strategy

- `main` — Stable / production-ready code only
- `dev` — Main development and integration branch
- `feature/*` — All new work happens on feature branches created from `dev`
  - Example: `feature/hw-interrogator`, `feature/improve-disk-detection`
- Never work directly on `main` or `dev` for new changes

**Rule:** Always create feature branches from the latest `dev`.

---

## Directory Structure

~/ansible/
├── ipa-elements/
│   └── hw-discovery/          # Custom DIB element for hardware discovery
├── roles/
│   ├── hw_collector/          # Flask/Gunicorn collector role
│   └── hw_discovery/          # (Legacy or supporting role)
├── playbooks/
├── environments/
│   └── dev/
├── docs/
├── PROJECT_NOTES.md
├── .gitignore
└── .gitattributes


---

## Key Technical Decisions

- Using **Ironic Python Agent (IPA)** + custom DIB element (`hw-discovery`) instead of custom Fedora Live ISO.
- Hardware collection runs automatically via systemd `oneshot` service on boot.
- Collector upgraded to **Gunicorn** (multi-worker) for handling multiple PXE clients.
- Strong/destructive disk wipe option available for ODF readiness (uses `wipefs`, `sgdisk`, `dd`, `blkdiscard`).
- External "Bastion Builder" code must **never** be committed into this repo.
- All hardware interrogation logic lives in `ipa-elements/hw-discovery/`.

---

## External Code / What Not to Commit

- Any "Bastion Builder" or external provisioning code from other repositories must stay **outside** this repo (e.g. in `~/external/`).
- Use `.gitignore` to protect against accidental commits of external code.

---

## Common Gotchas

- Git does **not** allow branch names like `dev/something` if a branch named `dev` already exists (ref lock error).
- Always use `feature/` prefix for new work (e.g. `feature/hw-interrogator`).
- When extracting tarballs or copying files, always verify paths before running copy commands.
- Disk wiping logic must be explicit and safe-by-default.

---

## Current Focus (as of July 2026)

- Improving the `hw-discovery` element with richer hardware data collection.
- Preparing for future integration with automated OpenShift (air-gapped) installation.
- Maintaining clean separation between this repo and any external bastion builder code.


## Managing PROJECT_NOTES.md

Use the following prompt patterns when you want to update or maintain this file:

### Adding Specific Content
Use this style when you already know exactly what you want added:
"Add the following to PROJECT_NOTES.md under the [Section Name] section:
- Point 1
- Point 2
- Detailed explanation..."

### Asking for Suggestions or Summaries
Use this style when you want me to think and propose content:
"Review our recent discussion about X and suggest what should be added to PROJECT_NOTES.md."
"Summarize the key decisions we made about Y and propose updates for PROJECT_NOTES.md."
"What important context from our last few conversations should be captured in PROJECT_NOTES.md?"

### General Maintenance Prompts
"Review PROJECT_NOTES.md for outdated information and suggest updates."
"Reorganize the [Section] in PROJECT_NOTES.md to be clearer."
"Add a new section to PROJECT_NOTES.md called 'Z' with relevant details from our discussion."

Tip: After I propose changes, you can say:
- "Apply those changes to PROJECT_NOTES.md"
- "Use your suggested version"
- Or give corrections and say "Update PROJECT_NOTES.md with these changes instead"

