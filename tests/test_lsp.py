"""End-to-end test for the stdio language server."""

import json
import subprocess
import sys
import unittest


SOURCE = """\
; Jump unconditionally.
.macro jmp target
    subleq zero, zero, target
.endm

zero: .word 0
main:
    jmp @done
@done: .word 0
"""


def frame(message: dict) -> bytes:
    """Encode one JSON-RPC message using LSP framing."""
    body = json.dumps(message, separators=(",", ":")).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def parse_frames(output: bytes) -> list[dict]:
    """Decode all LSP messages emitted by the test server."""
    messages = []
    remainder = output
    while remainder:
        header, separator, remainder = remainder.partition(b"\r\n\r\n")
        if not separator:
            break
        content_length = next(
            int(line.split(b":", 1)[1].strip())
            for line in header.split(b"\r\n")
            if line.lower().startswith(b"content-length:")
        )
        body, remainder = remainder[:content_length], remainder[content_length:]
        messages.append(json.loads(body))
    return messages


class LanguageServerTests(unittest.TestCase):
    """The installed server should speak LSP and expose its core features."""

    def test_stdio_hover_definition_diagnostics_and_inlay_hints(self) -> None:
        uri = "file:///subleq-lsp-test.s"
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": None,
                    "capabilities": {},
                },
            },
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "subleq",
                        "version": 1,
                        "text": SOURCE,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": {"line": 7, "character": 6},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/definition",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": {"line": 7, "character": 6},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "textDocument/inlayHint",
                "params": {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 8, "character": 20},
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "textDocument/semanticTokens/full",
                "params": {"textDocument": {"uri": uri}},
            },
            {"jsonrpc": "2.0", "id": 6, "method": "shutdown", "params": None},
            {"jsonrpc": "2.0", "method": "exit", "params": None},
        ]

        process = subprocess.run(
            [sys.executable, "-m", "subleq.cli", "lsp", "--stdio"],
            input=b"".join(frame(message) for message in messages),
            capture_output=True,
            check=False,
            timeout=10,
        )
        responses = parse_frames(process.stdout)
        by_id = {message.get("id"): message for message in responses if "id" in message}

        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertIn("hoverProvider", by_id[1]["result"]["capabilities"])
        self.assertIn("semanticTokensProvider", by_id[1]["result"]["capabilities"])
        self.assertIn("Jump unconditionally.", by_id[2]["result"]["contents"]["value"])
        self.assertEqual(by_id[3]["result"]["range"]["start"]["line"], 1)
        self.assertEqual(by_id[4]["result"][0]["label"], ": 1 instruction")
        semantic_data = by_id[5]["result"]["data"]
        token_types = by_id[1]["result"]["capabilities"]["semanticTokensProvider"][
            "legend"
        ]["tokenTypes"]
        self.assertIn("label", token_types)
        self.assertIn(token_types.index("label"), semantic_data[3::5])
        self.assertIn(token_types.index("macro"), semantic_data[3::5])
        self.assertIn(token_types.index("keyword"), semantic_data[3::5])
        decoded_tokens = []
        line = 0
        start = 0
        for offset in range(0, len(semantic_data), 5):
            delta_line, delta_start, length, token_type, _ = semantic_data[
                offset : offset + 5
            ]
            line += delta_line
            start = start + delta_start if delta_line == 0 else delta_start
            decoded_tokens.append((line, start, length, token_types[token_type]))
        self.assertIn((7, 4, 3, "macro"), decoded_tokens)
        self.assertIn((7, 8, 5, "label"), decoded_tokens)

        diagnostics = next(
            message
            for message in responses
            if message.get("method") == "textDocument/publishDiagnostics"
        )
        self.assertEqual(diagnostics["params"]["diagnostics"], [])


if __name__ == "__main__":
    unittest.main()
