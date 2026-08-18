"""Section profiles: built-ins + default custom kind."""

SECTION_REGISTRY: dict[str, dict] = {
    "experience": {
        "kind": "experience",
        "title": "Experience",
        "idPrefix": "exp_",
        "requiredFields": ["company", "title"],
        "intakeFields": [
            "company",
            "title",
            "location",
            "startDate",
            "endDate",
            "bullets",
        ],
        "optionalFields": [
            "location",
            "startDate",
            "endDate",
            "bullets",
            "categories",
            "skills",
            "status",
        ],
        "labelFields": ["company", "title"],
        "enrich": True,
        "polishBullets": True,
        "allowAdd": True,
        "allowExclude": True,
    },
    "projects": {
        "kind": "project",
        "title": "Projects",
        "idPrefix": "proj_",
        "requiredFields": ["name"],
        "intakeFields": [
            "name",
            "description",
            "technologies",
            "bullets",
            "url",
        ],
        "optionalFields": [
            "description",
            "technologies",
            "bullets",
            "url",
            "categories",
            "skills",
            "status",
        ],
        "labelFields": ["name"],
        "enrich": True,
        "polishBullets": True,
        "allowAdd": True,
        "allowExclude": True,
    },
    "education": {
        "kind": "credential",
        "title": "Education",
        "idPrefix": "edu_",
        "requiredFields": ["institution", "degree"],
        "intakeFields": [
            "institution",
            "degree",
            "location",
            "startDate",
            "endDate",
        ],
        "optionalFields": ["location", "startDate", "endDate", "details", "status"],
        "labelFields": ["degree", "institution"],
        "enrich": False,
        "polishBullets": False,
        "allowAdd": True,
        "allowExclude": True,
    },
    "achievements": {
        "kind": "achievement",
        "title": "Achievements",
        "idPrefix": "ach_",
        "requiredFields": ["title"],
        "intakeFields": ["title", "date", "description"],
        "optionalFields": ["date", "description", "status"],
        "labelFields": ["title"],
        "enrich": False,
        "polishBullets": False,
        "allowAdd": True,
        "allowExclude": True,
    },
}

CUSTOM_SECTION_DEFAULTS: dict = {
    "kind": "custom",
    "idPrefix": "item_",
    "requiredFields": ["title"],
    "intakeFields": ["title", "date", "description"],
    "optionalFields": ["date", "description", "status"],
    "labelFields": ["title"],
    "enrich": False,
    "polishBullets": False,
    "allowAdd": True,
    "allowExclude": True,
}

BUILTIN_SECTION_ORDER = ["experience", "projects", "education", "achievements"]


def get_section_profile(section: str) -> dict:
    if section in SECTION_REGISTRY:
        return dict(SECTION_REGISTRY[section])
    # Unknown key → custom defaults (section must already exist on payload for ops)
    profile = dict(CUSTOM_SECTION_DEFAULTS)
    profile["title"] = section.replace("_", " ").title()
    return profile


def empty_sections_bag() -> dict:
    return {
        key: {"title": meta["title"], "items": []}
        for key, meta in SECTION_REGISTRY.items()
    }


def empty_included_ids() -> dict:
    return {key: [] for key in SECTION_REGISTRY}


def format_unknown_section(section: str, known: dict | list | tuple) -> str:
    keys = list(known) if not isinstance(known, dict) else list(known)
    listed = ", ".join(keys) if keys else "(none)"
    return f"unknown section {section!r}. Use one of: {listed}"