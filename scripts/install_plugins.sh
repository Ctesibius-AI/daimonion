#!/bin/bash
# Bulk install ALL Anthropic plugins for Daimonion-Pythia
# Run from inside Claude Code: ! bash ~/daimonion/scripts/install_plugins.sh

PLUGINS=(
  "agent-sdk-dev"
  "clangd-lsp"
  "claude-code-setup"
  "claude-md-management"
  "code-review"
  "code-simplifier"
  "commit-commands"
  "csharp-lsp"
  "example-plugin"
  "explanatory-output-style"
  "feature-dev"
  "frontend-design"
  "gopls-lsp"
  "hookify"
  "jdtls-lsp"
  "kotlin-lsp"
  "learning-output-style"
  "lua-lsp"
  "math-olympiad"
  "mcp-server-dev"
  "php-lsp"
  "playground"
  "plugin-dev"
  "pr-review-toolkit"
  "pyright-lsp"
  "ralph-loop"
  "ruby-lsp"
  "rust-analyzer-lsp"
  "security-guidance"
  "session-report"
  "skill-creator"
  "swift-lsp"
  "typescript-lsp"
)

echo "Installing all ${#PLUGINS[@]} plugins..."
for p in "${PLUGINS[@]}"; do
  echo "  → $p"
  claude plugin install "$p@claude-plugins-official" --scope project --project ~/daimonion-pythia 2>/dev/null || true
done
echo ""
echo "Done. If any failed, install them interactively via /plugin install in Claude Code."
