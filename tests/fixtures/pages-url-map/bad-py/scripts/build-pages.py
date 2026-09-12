"""Fixture: catch-all non-main dest under /preview/<slug>/."""


def dest_for(branch: str) -> str:
    if branch == "main":
        return "/"
    slug = branch.replace("/", "--")
    return f"/preview/{slug}/"
