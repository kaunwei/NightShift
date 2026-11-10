"""Optional declarations for project-owned evidence adapters, never discovery."""


def validate(value):
    if (not isinstance(value, dict) or set(value) - {"frameworks", "case_selection"}
            or not isinstance(value.get("frameworks"), list) or not value["frameworks"]):
        raise ValueError("capabilities requires frameworks and optional case_selection")
    seen, prefixes = set(), set()
    for item in value["frameworks"]:
        if not isinstance(item, dict) or set(item) != {"name", "id_prefixes"}:
            raise ValueError("framework capability requires name and id_prefixes")
        name, ids = item["name"], item["id_prefixes"]
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("framework names must be unique and nonempty")
        if (not isinstance(ids, list) or not ids or any(not isinstance(p, str) or not p for p in ids)
                or len(set(ids)) != len(ids) or prefixes.intersection(ids)):
            raise ValueError("framework ID prefixes must be unique nonempty strings")
        seen.add(name)
        prefixes.update(ids)
    if "case_selection" in value and type(value["case_selection"]) is not bool:
        raise ValueError("case_selection capability must be boolean")
    return value


def supports(value, identity):
    return any(identity.startswith(prefix) for item in value["frameworks"] for prefix in item["id_prefixes"])
