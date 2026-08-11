# SUBLEQ Language Support for VS Code

This extension registers the `subleq` language and starts the Python language
server included in the parent SUBLEQ project.

By default the client locates the SUBLEQ project containing the active file and
launches `uv run --project <project> subleq lsp`. This also works when the
repository is opened through a parent or multi-root workspace.

## Development

From the repository root:

```powershell
uv sync
cd editors/vscode
npm install
```

Open the repository in VS Code, select **Run SUBLEQ Extension** in the Run and
Debug view, and press `F5`. The Extension Development Host opens the repository
with `*.s` associated with SUBLEQ.

## Package and install

```powershell
cd editors/vscode
npm run package
code --install-extension ../../dist/subleq-language-support.vsix
```

Reload VS Code after installation. This repository's `.vscode/settings.json`
maps `*.s` to `subleq`; the extension itself only claims `.subleq` globally.
Macro blocks receive contextual highlighting, and both global and private
label definitions use a theme-recognized definition scope. Canonical private
labels begin with `@`.

Use **SUBLEQ: Restart Language Server** from the command palette after changing
the server command or arguments. Protocol logs are available in the
**SUBLEQ Language Server** Output channel; set `subleq.trace.server` to
`verbose` for full message tracing.
