# Changelog

## v0.1.0 - Open-source baseline

Initial RheoFlow-Agent open-source preparation.

### Added

- RheoFlow-Agent project naming and README.
- Open-source `.gitignore` for runtime outputs, secrets, and generated vector indices.
- Third-party notices file.
- Documentation for architecture, quick start, capability boundaries, provider configuration, RheoTool templates, and benchmark planning.
- Compatibility script alias `rheoflow-agent-mcp` while retaining `foamagent-mcp`.

### Notes

- Internal runtime artifacts, generated FAISS indices, training materials, and large local case assets are excluded from the initial repository.
- Historical `FOAMAGENT_*` environment variables are retained for compatibility.
