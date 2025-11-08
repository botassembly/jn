# Custom JC Parser Example

This example demonstrates how to create a custom JC parser for the JN pipeline system.

## Overview

JC (JSON Convert) allows you to create custom parsers for non-standard text formats. This example shows how to create a parser for a simple key-value format.

## Custom Parser: Key-Value Format

**Input format:**
```
name: John Doe
age: 30
city: New York
status: active
```

**Output (JSON):**
```json
{
  "name": "John Doe",
  "age": "30",
  "city": "New York",
  "status": "active"
}
```

## Directory Structure

```
examples/custom-jc-parser/
├── README.md                 # This file
├── jcparsers/               # Custom JC parsers directory
│   └── keyvalue.py          # Custom key-value parser
├── setup.sh                 # Setup script to install the parser
├── test_data.txt            # Sample input data
└── demo.sh                  # Demo script showing usage
```

## Installation

1. Install jc if not already installed:
```bash
pip install jc
# or
uv pip install jc
```

2. Set up the custom parser:
```bash
cd examples/custom-jc-parser
./setup.sh
```

This will copy the custom parser to the JC plugin directory.

## Usage

### Standalone (with jc command)

```bash
# Parse key-value data
cat test_data.txt | jc --keyvalue

# Or use the Python API
python3 -c "
import jc
data = open('test_data.txt').read()
print(jc.parse('keyvalue', data))
"
```

### With JN Pipeline

```bash
# Initialize JN config
jn init

# Create a source using the custom parser via jc adapter
jn new source exec user_data --adapter jc --argv cat --argv test_data.txt

# Note: For the jc adapter to find your custom parser, you need to:
# 1. Either use the Python API directly (see jcparsers/keyvalue.py)
# 2. Or modify jc to recognize 'keyvalue' as a registered parser
#
# For demonstration, we'll use a shell source that calls jc directly:

jn new source shell parse_keyvalue \
  --cmd "cat test_data.txt | jc --keyvalue" \

# Create a converter to extract specific fields
jn new converter extract_name --expr '.name'

# Create a target
jn new target exec stdout --argv cat

# Create and run the pipeline
jn new pipeline user_info --source parse_keyvalue --converter extract_name --target stdout
jn run user_info --unsafe-shell
```

## Files

### jcparsers/keyvalue.py

The custom parser implementation. This parser:
- Reads line-by-line
- Splits on first `:` character
- Returns a dictionary of key-value pairs

### test_data.txt

Sample input data in key-value format.

### setup.sh

Copies the parser to the appropriate JC plugin directory based on your OS:
- Linux/Unix: `~/.local/share/jc/jcparsers`
- macOS: `~/Library/Application Support/jc/jcparsers`
- Windows: `%LOCALAPPDATA%\jc\jc\jcparsers`

## Testing

Run the demo script to see the parser in action:
```bash
./demo.sh
```

## Creating Your Own Parser

1. Copy `jcparsers/keyvalue.py` as a template
2. Modify the `parse()` function to handle your format
3. Update the `info` class with your parser's metadata
4. Run `./setup.sh` to install it
5. Use it in your JN pipelines!

## References

- [JC Documentation](https://kellyjonbrazil.github.io/jc/)
- [JC Library Guide](../../spec/arch/jc-library-guide.md)
- [JN Adapters Architecture](../../spec/arch/adapters.md)
