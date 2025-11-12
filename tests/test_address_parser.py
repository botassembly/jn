"""Unit tests for address parsing."""

import pytest

from src.jn.addressing import Address, parse_address


class TestBasicParsing:
    """Test basic address parsing without operators."""

    def test_simple_file(self):
        """Test parsing simple file path."""
        addr = parse_address("data.csv")
        assert addr.base == "data.csv"
        assert addr.format_override is None
        assert addr.parameters == {}
        assert addr.type == "file"

    def test_absolute_path(self):
        """Test parsing absolute file path."""
        addr = parse_address("/absolute/path/data.json")
        assert addr.base == "/absolute/path/data.json"
        assert addr.type == "file"

    def test_relative_path(self):
        """Test parsing relative file path."""
        addr = parse_address("./relative/data.yaml")
        assert addr.base == "./relative/data.yaml"
        assert addr.type == "file"

    def test_stdin(self):
        """Test parsing stdin."""
        addr = parse_address("-")
        assert addr.base == "-"
        assert addr.type == "stdio"

    def test_http_url(self):
        """Test parsing HTTP URL."""
        addr = parse_address("http://example.com/data.json")
        assert addr.base == "http://example.com/data.json"
        assert addr.type == "protocol"

    def test_https_url(self):
        """Test parsing HTTPS URL."""
        addr = parse_address("https://api.example.com/data.csv")
        assert addr.base == "https://api.example.com/data.csv"
        assert addr.type == "protocol"

    def test_s3_url(self):
        """Test parsing S3 URL."""
        addr = parse_address("s3://bucket/key.json")
        assert addr.base == "s3://bucket/key.json"
        assert addr.type == "protocol"

    def test_gmail_url(self):
        """Test parsing Gmail URL."""
        addr = parse_address("gmail://me/messages")
        assert addr.base == "gmail://me/messages"
        assert addr.type == "protocol"

    def test_profile_reference(self):
        """Test parsing profile reference."""
        addr = parse_address("@genomoncology/alterations")
        assert addr.base == "@genomoncology/alterations"
        assert addr.type == "profile"

    def test_plugin_reference(self):
        """Test parsing plugin reference."""
        addr = parse_address("@json")
        assert addr.base == "@json"
        assert addr.type == "plugin"


class TestFormatOverride:
    """Test format override with ~ operator."""

    def test_format_override_file(self):
        """Test format override on file."""
        addr = parse_address("data.txt~csv")
        assert addr.base == "data.txt"
        assert addr.format_override == "csv"
        assert addr.type == "file"

    def test_format_override_stdin(self):
        """Test format override on stdin."""
        addr = parse_address("-~csv")
        assert addr.base == "-"
        assert addr.format_override == "csv"
        assert addr.type == "stdio"

    def test_format_override_json(self):
        """Test JSON format override."""
        addr = parse_address("data.unknown~json")
        assert addr.base == "data.unknown"
        assert addr.format_override == "json"

    def test_format_override_table(self):
        """Test table format override."""
        addr = parse_address("-~table")
        assert addr.base == "-"
        assert addr.format_override == "table"

    def test_multiple_tildes(self):
        """Test multiple tildes (should use last one)."""
        addr = parse_address("data~foo~csv")
        assert addr.base == "data~foo"
        assert addr.format_override == "csv"

    def test_empty_format_override(self):
        """Test empty format override (should raise error)."""
        with pytest.raises(ValueError, match="Format override cannot be empty"):
            parse_address("data.csv~")


class TestParameters:
    """Test parameter parsing with ? operator."""

    def test_single_parameter(self):
        """Test single parameter."""
        addr = parse_address("data.csv?delimiter=;")
        assert addr.base == "data.csv"
        assert addr.parameters == {"delimiter": ";"}

    def test_multiple_parameters(self):
        """Test multiple parameters."""
        addr = parse_address("data.csv?delimiter=;&header=false")
        assert addr.base == "data.csv"
        assert addr.parameters == {"delimiter": ";", "header": "false"}

    def test_parameters_with_equals(self):
        """Test parameter value containing equals sign."""
        addr = parse_address("@api/source?filter=status=active")
        assert addr.parameters == {"filter": "status=active"}

    def test_url_encoded_parameters(self):
        """Test URL-encoded parameters."""
        addr = parse_address("data.csv?delimiter=%3B")  # %3B = semicolon
        assert addr.parameters == {"delimiter": ";"}

    def test_empty_parameter_value(self):
        """Test empty parameter value."""
        addr = parse_address("data.csv?key=")
        assert addr.parameters == {"key": ""}

    def test_parameter_without_value(self):
        """Test parameter without equals sign."""
        addr = parse_address("data.csv?standalone")
        assert addr.parameters == {"standalone": ""}


class TestShorthandFormats:
    """Test shorthand format expansion."""

    def test_table_grid_shorthand(self):
        """Test table.grid shorthand."""
        addr = parse_address("-~table.grid")
        assert addr.base == "-"
        assert addr.format_override == "table"
        assert addr.parameters == {"tablefmt": "grid"}

    def test_table_markdown_shorthand(self):
        """Test table.markdown shorthand."""
        addr = parse_address("-~table.markdown")
        assert addr.base == "-"
        assert addr.format_override == "table"
        assert addr.parameters == {"tablefmt": "markdown"}

    def test_table_html_shorthand(self):
        """Test table.html shorthand."""
        addr = parse_address("-~table.html")
        assert addr.format_override == "table"
        assert addr.parameters == {"tablefmt": "html"}


class TestCombinedOperators:
    """Test combining ~ and ? operators."""

    def test_format_and_parameters(self):
        """Test format override + parameters."""
        addr = parse_address("data.txt~csv?delimiter=;")
        assert addr.base == "data.txt"
        assert addr.format_override == "csv"
        assert addr.parameters == {"delimiter": ";"}

    def test_stdin_format_and_parameters(self):
        """Test stdin with format and parameters."""
        # Note: In URL query strings, literal \t is two characters, not a tab
        # Users should use URL encoding (%09) or actual tab character for tabs
        addr = parse_address("-~csv?delimiter=%09")  # %09 = tab
        assert addr.base == "-"
        assert addr.format_override == "csv"
        assert addr.parameters == {"delimiter": "\t"}

    def test_shorthand_and_parameters(self):
        """Test shorthand + additional parameters."""
        addr = parse_address("-~table.grid?maxcolwidths=20")
        assert addr.format_override == "table"
        assert addr.parameters == {"tablefmt": "grid", "maxcolwidths": "20"}

    def test_profile_with_format_and_parameters(self):
        """Test profile with format override and parameters."""
        addr = parse_address("@api/source~json?limit=100")
        assert addr.base == "@api/source"
        assert addr.format_override == "json"
        assert addr.parameters == {"limit": "100"}
        assert addr.type == "profile"


class TestProfileReferences:
    """Test profile reference parsing."""

    def test_profile_with_parameters(self):
        """Test profile with query parameters."""
        addr = parse_address("@genomoncology/alterations?gene=BRAF")
        assert addr.base == "@genomoncology/alterations"
        assert addr.parameters == {"gene": "BRAF"}
        assert addr.type == "profile"

    def test_profile_multiple_parameters(self):
        """Test profile with multiple parameters."""
        addr = parse_address("@api/source?gene=BRAF&limit=100")
        assert addr.parameters == {"gene": "BRAF", "limit": "100"}

    def test_gmail_profile(self):
        """Test Gmail profile reference."""
        addr = parse_address("@gmail/inbox?from=boss&is=unread")
        assert addr.base == "@gmail/inbox"
        assert addr.parameters == {"from": "boss", "is": "unread"}
        assert addr.type == "profile"


class TestProtocolUrls:
    """Test protocol URL parsing."""

    def test_http_with_query_string(self):
        """Test HTTP URL with query string."""
        addr = parse_address("http://example.com/data.json?key=value")
        assert addr.base == "http://example.com/data.json"
        assert addr.parameters == {"key": "value"}

    def test_s3_with_region(self):
        """Test S3 URL with region parameter."""
        addr = parse_address("s3://bucket/key.json?region=us-west-2")
        assert addr.base == "s3://bucket/key.json"
        assert addr.parameters == {"region": "us-west-2"}

    def test_gmail_protocol_with_search(self):
        """Test Gmail protocol URL with search parameters."""
        addr = parse_address("gmail://me/messages?from=boss&is=unread")
        assert addr.base == "gmail://me/messages"
        assert addr.parameters == {"from": "boss", "is": "unread"}


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_string(self):
        """Test empty string raises error."""
        with pytest.raises(ValueError, match="Address cannot be empty"):
            parse_address("")

    def test_whitespace_only(self):
        """Test whitespace-only string raises error."""
        with pytest.raises(ValueError, match="Address cannot be empty"):
            parse_address("   ")

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed."""
        addr = parse_address("  data.csv  ")
        assert addr.base == "data.csv"

    def test_file_with_tilde_in_name(self):
        """Test file with tilde in name (before last ~)."""
        addr = parse_address("data~backup.txt~csv")
        assert addr.base == "data~backup.txt"
        assert addr.format_override == "csv"

    def test_url_with_fragment(self):
        """Test URL with fragment (treated as part of base)."""
        addr = parse_address("http://example.com/page#section")
        assert addr.base == "http://example.com/page#section"

    def test_special_characters_in_path(self):
        """Test special characters in file path."""
        addr = parse_address("data (2024).csv")
        assert addr.base == "data (2024).csv"

    def test_unicode_in_path(self):
        """Test Unicode characters in path."""
        addr = parse_address("données.csv")
        assert addr.base == "données.csv"


class TestValidation:
    """Test address validation."""

    def test_profile_vs_plugin(self):
        """Test that @name without slash is plugin, not profile."""
        # @name (no slash) = plugin
        addr = parse_address("@profile")
        assert addr.type == "plugin"
        assert addr.base == "@profile"

    def test_invalid_profile_multiple_slashes(self):
        """Test invalid profile with multiple slashes."""
        with pytest.raises(ValueError, match="must be @namespace/component"):
            parse_address("@namespace/component/extra")

    def test_invalid_protocol_no_colon_slash(self):
        """Test protocol must have ://."""
        # Note: This is actually a valid file path, not a protocol
        addr = parse_address("http/file.csv")
        assert addr.type == "file"  # Not protocol

    def test_empty_profile_namespace(self):
        """Test empty profile namespace."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_address("@/component")

    def test_empty_profile_component(self):
        """Test empty profile component."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_address("@namespace/")

    def test_plugin_vs_profile_with_slash(self):
        """Test that @name/component is profile, validates correctly."""
        # @name/component (with slash) = profile, must have both parts non-empty
        with pytest.raises(ValueError, match="must be @namespace/component"):
            parse_address("@namespace/component/extra")  # Too many slashes


class TestStringRepresentation:
    """Test string representation of Address."""

    def test_str_simple(self):
        """Test string representation of simple address."""
        addr = parse_address("data.csv")
        assert str(addr) == "data.csv"

    def test_str_with_format(self):
        """Test string representation with format override."""
        addr = parse_address("data.txt~csv")
        assert str(addr) == "data.txt~csv"

    def test_str_with_parameters(self):
        """Test string representation with parameters."""
        addr = parse_address("data.csv?delimiter=;")
        # Note: Order may vary, so just check components are present
        s = str(addr)
        assert s.startswith("data.csv?")
        assert "delimiter=;" in s

    def test_str_with_all(self):
        """Test string representation with all components."""
        addr = parse_address("data.txt~csv?delimiter=;")
        s = str(addr)
        assert "data.txt~csv" in s
        assert "delimiter=;" in s


class TestRealWorldExamples:
    """Test real-world usage examples from spec."""

    def test_csv_with_semicolon(self):
        """Test semicolon-delimited CSV."""
        addr = parse_address("data.txt~csv?delimiter=;")
        assert addr.base == "data.txt"
        assert addr.format_override == "csv"
        assert addr.parameters["delimiter"] == ";"

    def test_stdin_csv(self):
        """Test stdin as CSV."""
        addr = parse_address("-~csv")
        assert addr.base == "-"
        assert addr.format_override == "csv"
        assert addr.type == "stdio"

    def test_stdout_grid_table(self):
        """Test stdout as grid table."""
        addr = parse_address("-~table.grid")
        assert addr.base == "-"
        assert addr.format_override == "table"
        assert addr.parameters["tablefmt"] == "grid"

    def test_api_with_limit(self):
        """Test API call with limit parameter."""
        addr = parse_address("@genomoncology/alterations?gene=BRAF&limit=100")
        assert addr.type == "profile"
        assert addr.parameters["gene"] == "BRAF"
        assert addr.parameters["limit"] == "100"

    def test_gmail_unread(self):
        """Test Gmail unread messages."""
        addr = parse_address("@gmail/inbox?from=boss&is=unread")
        assert addr.type == "profile"
        assert addr.parameters["from"] == "boss"
        assert addr.parameters["is"] == "unread"

    def test_json_with_indent(self):
        """Test JSON with indentation."""
        addr = parse_address("output.json?indent=4")
        assert addr.base == "output.json"
        assert addr.parameters["indent"] == "4"

    def test_table_with_config(self):
        """Test table with multiple config options."""
        addr = parse_address("-~table?tablefmt=grid&maxcolwidths=20&showindex=true")
        assert addr.format_override == "table"
        assert addr.parameters["tablefmt"] == "grid"
        assert addr.parameters["maxcolwidths"] == "20"
        assert addr.parameters["showindex"] == "true"
