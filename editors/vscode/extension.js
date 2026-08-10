"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vscode = require("vscode");
const {
  LanguageClient,
  RevealOutputChannelOn,
  TransportKind,
} = require("vscode-languageclient/node");

let client;

function findProjectRoot(start) {
  if (!start) {
    return undefined;
  }

  let directory = path.resolve(start);
  while (true) {
    if (
      fs.existsSync(path.join(directory, "pyproject.toml")) &&
      fs.existsSync(path.join(directory, "subleq", "lsp.py"))
    ) {
      return directory;
    }

    const parent = path.dirname(directory);
    if (parent === directory) {
      return undefined;
    }
    directory = parent;
  }
}

function projectRoot() {
  const activeDocument = vscode.window.activeTextEditor?.document;
  if (activeDocument?.uri.scheme === "file") {
    const root = findProjectRoot(path.dirname(activeDocument.uri.fsPath));
    if (root) {
      return root;
    }
  }

  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    const root = findProjectRoot(folder.uri.fsPath);
    if (root) {
      return root;
    }
  }

  return undefined;
}

function createClient() {
  const configuration = vscode.workspace.getConfiguration("subleq");
  const command = configuration.get("server.command", "uv");
  const configuredArguments = configuration.get("server.arguments", []);
  const root = projectRoot();
  const args =
    Array.isArray(configuredArguments) && configuredArguments.length > 0
      ? configuredArguments.map(String)
      : ["run", ...(root ? ["--project", root] : []), "subleq", "lsp"];

  const serverOptions = {
    command,
    args,
    transport: TransportKind.stdio,
    options: root ? { cwd: root } : undefined,
  };
  const clientOptions = {
    documentSelector: [
      { scheme: "file", language: "subleq" },
      { scheme: "untitled", language: "subleq" },
    ],
    revealOutputChannelOn: RevealOutputChannelOn.Error,
  };

  return new LanguageClient(
    "subleq",
    "SUBLEQ Language Server",
    serverOptions,
    clientOptions,
  );
}

async function startClient() {
  client = createClient();
  try {
    await client.start();
  } catch (error) {
    client = undefined;
    const message = error instanceof Error ? error.message : String(error);
    void vscode.window.showErrorMessage(
      `Unable to start the SUBLEQ language server: ${message}`,
    );
  }
}

async function restartClient() {
  if (client) {
    await client.stop();
    client = undefined;
  }
  await startClient();
}

async function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "subleq.restartLanguageServer",
      restartClient,
    ),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (
        event.affectsConfiguration("subleq.server.command") ||
        event.affectsConfiguration("subleq.server.arguments")
      ) {
        void restartClient();
      }
    }),
  );
  await startClient();
}

async function deactivate() {
  if (client) {
    await client.stop();
    client = undefined;
  }
}

module.exports = { activate, deactivate };
