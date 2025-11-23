#!/bin/bash
# MCP Demo - Model Context Protocol Integration
# This demo shows how to connect to MCP servers using JN's profile system

echo "=== MCP Demo Examples ==="
echo ""

echo "1. List tools from BioMCP (requires BioMCP installation):"
echo "   jn cat '@biomcp?list=tools'"
echo ""

echo "2. Search biomedical data:"
echo "   jn cat '@biomcp/search?gene=BRAF&disease=Melanoma'"
echo ""

echo "3. Get code documentation (requires Context7):"
echo "   jn cat '@context7/search?library=mcp'"
echo ""

echo "4. Pipeline example - search and filter:"
echo "   jn cat '@biomcp/search?gene=BRAF' | jn filter '.text | contains(\"Phase 3\")' | jn put results.json"
echo ""

echo "See README.md for full documentation and setup instructions"
