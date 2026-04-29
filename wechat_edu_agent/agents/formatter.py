from __future__ import annotations


class Formatter:
    def apply_title(self, article_markdown: str, final_title: str) -> str:
        content = (article_markdown or "").strip()
        if content.startswith("# "):
            lines = content.splitlines()
            lines[0] = f"# {final_title}"
            return "\n".join(lines).strip() + "\n"
        return f"# {final_title}\n\n{content}\n"
