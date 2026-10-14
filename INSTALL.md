# Installation and Team Distribution

## Package structure

Extracting the complete archive creates `synbio-igem-skills-v1.1.0`, containing six Skills under `skills/`. A single-Skill archive extracts to a folder named after that Skill. Preserve `SKILL.md`, `agents`, `docs`, and any included `references`, `assets`, or `scripts` directories.

Install the complete Skill folder. Do not copy only `SKILL.md` or merge multiple Skills into one folder. If a folder with the same name already exists, compare and back it up before replacing it; do not overwrite team customizations blindly.

## Local use with Codex

According to the [OpenAI Skills documentation](https://developers.openai.com/codex/skills), retrieved on 2026-09-14, personal Skills can be placed in `.agents/skills` under the user directory, while project Skills can be placed in the project's `.agents/skills` directory. Copy the desired Skill folders there; for example, verify that `.agents/skills/synbio-expert/SKILL.md` exists.

On Windows, locate the personal directory through the `USERPROFILE` environment variable. On macOS/Linux, use the current user's home directory. Follow the active client configuration if an organization or older installation specifies another location. This release package does not modify local configuration or install itself automatically.

Codex CLI/IDE can invoke a Skill with `$skill-name` or a Skill selector; ChatGPT uses the Skill selector supported by that product. Local scripts, web access, and standalone Skills depend on the host product and its configuration. If an updated Skill does not appear, restart the client as described in its official documentation.

## Other agents and chatbots

Hosts that support the `SKILL.md` convention can read these files. Otherwise, the developer must load the entry instructions and implement on-demand access to supporting files. Uploading a ZIP as a chat attachment does not guarantee that it has been installed. See the [iGEM chatbot integration guide](skills/igem-mentor/docs/Chatbot接入说明.md).

This is a local Skill distribution package. It does not include a marketplace manifest or marketplace submission. A marketplace release would need a separate package that follows that platform's requirements; this does not affect local Skill use.

## Script dependencies

- Knowledge base: Python 3.10+, standard library only; no cloud account required.
- Video: Python 3.9+ and FFmpeg with the required encoders; see its operation guide for commands and options.
- Cue cards: Python 3.10+. HTML mode uses the standard library; PDF mode requires ReportLab and a supported Chinese font, as described in its `requirements.txt` and guide.

Install third-party dependencies in your own virtual environment. Do not put personal keys, font files, databases, generated videos, or student records in the release directory. Licenses for external software are determined by their providers; this package does not include their binaries or fonts.

## Verify the installation

Ask the host to explain a concept, draft a course plan, and answer an iGEM question that requires cited sources; confirm that the intended Skill is selected. Run helper tools with `--help` before use, then verify them with the included examples. The date above describes the package's documentation basis; it does not mean the user's current session has checked the live web.
