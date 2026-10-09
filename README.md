# Swimler

Swimler is a local-first Python tool for anonymizing text in exported files. It
redacts email addresses and phone numbers with regular expressions, then uses a
local Ollama model to identify personal names and precise personal locations.
It preserves configured brand names and copies binary ZIP members unchanged.

This tool is an aid, not a guarantee of GDPR compliance. You are responsible
for reviewing its output. No external service is used. The Ollama client is
configured to connect only to `127.0.0.1`; install and run Ollama locally and
pull a model before processing sensitive data.

## Install

```shell
python -m pip install .
ollama pull llama3.2
```

## Usage

```shell
swimler exported.zip
swimler notes.txt --model llama3.2 --brand-word Swimler
swimler exported.zip -o ./cleaned -y
swimler contacts.csv --audit-log ./review/export.audit.log
```

The input can be a ZIP archive or UTF-8 text file. Text members are anonymized
and binary members remain unchanged. CSV, TSV, and TAB files are parsed as
delimited tables. The output keeps the input filename and defaults to a
`swimler-output` directory beside the input; `-o` selects another output
directory. Existing output files are not overwritten without confirmation
(or `-y`).

By default, Swimler presents a diff for each input file whose text changed.
Accept applies the changes, amend opens the cleaned file in `$EDITOR`, and
reject keeps the original file contents. Use `-y` to accept changes
automatically. The default model is `llama3.2`; use `--model` to select another
locally installed Ollama model. Add `--brand-word` once per brand to preserve.

An append-only `.audit.log` is written alongside the output by default. Use
`--audit-log` to select another path. It records file names, row and column
numbers, operation categories and counts, and decisions; it does not record
original text or detected personal-data values.
