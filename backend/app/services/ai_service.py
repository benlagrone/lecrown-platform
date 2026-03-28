def generate_post(input_text: str) -> str:
    lines = [
        "Sharp LinkedIn post draft:",
        "",
        input_text.strip(),
        "",
        "Point of view stays direct. Replace this stub with an LLM call when you're ready.",
    ]
    return "\n".join(lines)
