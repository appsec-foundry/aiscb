"""Markdown report of verification findings."""


def cell(text):
    """Encode text for one Markdown table cell."""
    text = " ".join(str(text).split())
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("\\", "\\\\"), ("|", "\\|")):
        text = text.replace(old, new)
    return text


def verification_table(result):
    lines = ["| Finding | CWE | Location | Reason |", "|---|---|---|---|"]
    for finding in result["verification_findings"]:
        location = f"{finding['file']}:{finding['line']}"
        lines.append(f"| {finding['id']} | {finding['cwe']} | {cell(location)} | {cell(finding['reason'])} |")
    return "\n".join(lines)
