import argparse
import re
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright


ACTION_DIR = Path(__file__).parent.resolve()
BUILT_IN_TEMPLATES_DIR = ACTION_DIR / "templates"


FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_markdown(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")

    match = FRONTMATTER_PATTERN.match(raw)

    if not match:
        return {}, raw

    metadata = yaml.safe_load(match.group(1)) or {}
    body = raw[match.end():]

    return metadata, body


def resolve_template(template_input: str, workspace: Path) -> Path:
    candidate_path = Path(template_input)

    if candidate_path.exists():
        return candidate_path.resolve()

    workspace_template = workspace / 'templates' / template_input
    if workspace_template.exists():
        return workspace_template.resolve()

    built_in_template = BUILT_IN_TEMPLATES_DIR / template_input
    if built_in_template.exists():
        return built_in_template.resolve()

    raise FileNotFoundError(
        f"Template '{template_input}' was not found. "
        f"Use a built-in template name or a path to a template directory."
    )


def markdown_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=[
            "extra",
            "sane_lists",
            "nl2br",
            "smarty",
        ],
    )


def render_html(template_dir: Path, metadata: dict, content: str) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )

    template = env.get_template("template.html")

    return template.render(
        meta=metadata,
        content=content,
    )


def export_pdf(html: str, template_dir: Path, output_path: Path) -> None:
    temp_html = output_path.with_suffix(".html")
    temp_html.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # browser = p.chromium.launch(
        #     executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        #     headless=True
        # )
        page = browser.new_page()

        page.goto(temp_html.as_uri(), wait_until="networkidle")

        page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            margin={
                "top": "16mm",
                "right": "15mm",
                "bottom": "16mm",
                "left": "15mm",
            },
        )

        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="MarkCV - Markdown to PDF CV generator")

    parser.add_argument("--input", required=True, help="Path to Markdown input file")
    parser.add_argument("--template", default="default", help="Template name or template directory path")
    parser.add_argument("--output", default="resume.pdf", help="Output PDF path")

    args = parser.parse_args()

    workspace = Path.cwd()
    input_path = (workspace / args.input).resolve()
    output_path = (workspace / args.output).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    template_dir = resolve_template(args.template, workspace)

    if not (template_dir / "template.html").exists():
        raise FileNotFoundError(f"Missing template.html in template directory: {template_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata, body = parse_markdown(input_path)
    html_content = markdown_to_html(body)
    rendered_html = render_html(template_dir, metadata, html_content)

    export_pdf(rendered_html, template_dir, output_path)

    print(f"CV generated: {output_path}")


if __name__ == "__main__":
    main()