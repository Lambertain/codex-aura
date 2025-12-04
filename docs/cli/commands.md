# CLI Commands

Codex Aura provides a command-line interface with several commands.

## Global Options

- `--help`: Show help message
- `--version`: Show version information
- `--verbose`: Enable verbose output
- `--config FILE`: Specify configuration file

## Available Commands

### analyze

Perform code analysis and generate dependency graphs.

```bash
codex-aura analyze [OPTIONS] [PATH]
```

See [Analyze Command](analyze.md) for details.

### serve

Start web server to explore graphs interactively.

```bash
codex-aura serve [OPTIONS] GRAPH_FILE
```

See [Serve Command](serve.md) for details.

### version

Show version information.

```bash
codex-aura version
```

### help

Show help for commands.

```bash
codex-aura help [COMMAND]
```

## Configuration

Commands can be configured via:

1. Command-line options
2. Configuration file (`codex-aura.toml` or `codex-aura.yaml`)
3. Environment variables (prefixed with `CODEX_AURA_`)

## Examples

Get help:

```bash
codex-aura --help
codex-aura analyze --help
```

Use configuration file:

```bash
codex-aura analyze --config my-config.toml
```

Verbose output:

```bash
codex-aura analyze --verbose .