# SynBio & iGEM Skills Collection

Version 1.1.0 · Release package prepared September 15, 2026

Six independent Skills for students, mentors, and education teams working in synthetic biology and iGEM. Each Skill includes a `SKILL.md`, agent metadata, an introduction, user guidance, and teaching guidance, with templates, examples, or scripts where useful.

| Skill | What it does | Requirements |
|---|---|---|
| [synbio-expert](skills/synbio-expert/docs/介绍.md) | Uses evidence cards for science Q&A, paper reading, and profiles of Chinese researchers. | A Skill-capable AI; current facts require web access or readable source material. |
| [synbio-planner](skills/synbio-planner/docs/介绍.md) | Plans projects, courses, and events with outcome maps, dependency maps, and evidence checkpoints. | A Skill-capable AI. |
| [igem-mentor](skills/igem-mentor/docs/介绍.md) | Provides bilingual, year- and role-aware iGEM evidence and action guidance. | A Skill-capable AI and access to relevant official sources. |
| [synbio-knowledge-base](skills/synbio-knowledge-base/docs/介绍.md) | Maintains a project-scoped local evidence ledger and reproducible keyword searches. | Python 3.10+; standard library only. |
| [synbio-video](skills/synbio-video/docs/介绍.md) | Maps scientific claims to shots, visual types, and production status. | Planning needs no script; rendering requires Python 3.9+ and FFmpeg. |
| [synbio-cue-cards](skills/synbio-cue-cards/docs/介绍.md) | Creates multi-person cue cards with triggers, evidence, and handoff actions. | HTML generation requires Python 3.10+; PDF output also needs ReportLab and a Chinese font. |

Start with the three core Skills, then add supporting modules as your deliverables require. The Skills can be installed independently; you do not need to load the entire collection into one conversation.

## Quick start

1. Follow [INSTALL.md](INSTALL.md) and keep each Skill's directory intact.
2. Call a Skill from your agent, for example: “Use `$synbio-planner` to design a four-session synthetic biology course for students with no lab experience.” Platform-specific invocation syntax is described in the installation guide.
3. Provide the task context and available sources. For current iGEM policies, ask for official sources from the relevant year.
4. Check each Skill's user guide for tool dependencies and commands. Tools do not run automatically just because a Skill is installed.

## Scope and limitations

- The initial researcher profiles cover Guoqiang Chen, Junbiao Dai, and Chongjun Qin, with official links and documented verification scope. The selection is not a ranking and does not imply endorsement or authorization.
- The iGEM module provides six workflow areas and starting points for research. Some official pages were only available through search excerpts or JavaScript-dependent pages; verification limitations are documented. Unverified fees and deadlines are not included.
- The local knowledge base supports keyword search and project filtering. It is not a cloud semantic-search service and does not provide authentication for public services.
- Video-generation services and MemOS cloud access are not bundled; connect only platforms you are authorized to use. The video script composes supplied assets and does not create experimental footage.
- Cue cards support structured text input and HTML/PDF output; lossless conversion of arbitrary Word documents, equations, or scientific figures is not promised.
- iGEM Mentor is a guidance layer that can be integrated with a chatbot. This package does not include a website, account backend, or automatic annual updates.

Scientific claims, competition rules, real experiments, interviews, and project attribution should be supported by genuine evidence. Examples are for teaching or tool demonstration and must not be presented as research completed by a team.

See [VALIDATION.md](VALIDATION.md) for test coverage, [ORIGINALITY-REVIEW.md](ORIGINALITY-REVIEW.md) for the independent redesign and similarity review, and [PROVENANCE.md](PROVENANCE.md) for source scope. Newly written materials are distributed under the [MIT License](LICENSE.txt). External papers, webpages, trademarks, fonts, and tools remain subject to their respective rights.
