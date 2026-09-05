import json
from typing import Set, Optional, List, Union
from app.models.agent import Agent


def parse_tags_json(tags_raw: Optional[str]) -> List[str]:
    """Safely deserializes JSON tags array into a clean list of lowercase tag strings."""
    if not tags_raw:
        return []
    try:
        data = json.loads(tags_raw)
        if isinstance(data, list):
            return [str(t).strip().lower() for t in data if str(t).strip()]
        if isinstance(data, str):
            return [str(data).strip().lower()]
    except Exception:
        return [t.strip().lower() for t in tags_raw.split(",") if t.strip()]
    return []


def parse_ids_json(raw: Optional[Union[str, List[int], List[str]]]) -> List[int]:
    """Safely deserializes JSON array of integer IDs."""
    if not raw:
        return []
    if isinstance(raw, list):
        out = []
        for x in raw:
            try:
                out.append(int(x))
            except (ValueError, TypeError):
                pass
        return sorted(list(set(out)))
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            out = []
            for x in data:
                try:
                    out.append(int(x))
                except (ValueError, TypeError):
                    pass
            return sorted(list(set(out)))
        elif isinstance(data, (int, str)):
            return [int(data)]
    except Exception:
        pass
    return []


def get_agent_group_ids(agent: Agent) -> List[int]:
    """Returns list of all assigned Access Group IDs for an agent."""
    ids = set(parse_ids_json(getattr(agent, "group_ids_json", "[]")))
    if getattr(agent, "group_id", None):
        ids.add(agent.group_id)
    return sorted(list(ids))


def get_effective_agent_tags(agent: Agent) -> Set[str]:
    """Returns consolidated set of access identifiers (group IDs, group names, tags) for an agent."""
    tags = set(parse_tags_json(getattr(agent, "access_tags_json", "[]")))

    # Add group IDs as strings e.g. "1", "2"
    for gid in get_agent_group_ids(agent):
        tags.add(str(gid))

    if getattr(agent, "group", None):
        if agent.group.name:
            tags.add(agent.group.name.strip().lower())
        if getattr(agent.group, "tags_json", None):
            tags.update(parse_tags_json(agent.group.tags_json))

    return tags


def filter_items_by_access_tags(items: list, allowed_tags: Set[str], tag_attr: str = "access_tags_json") -> list:
    """Filters a list of models or dicts in-memory by access tags / access group IDs.
    Items with empty access scope are globally accessible to all agents.
    Items with specific access groups/tags require at least one match with the agent's effective scope."""
    result = []
    for item in items:
        # Check access_group_ids_json
        raw_group_ids = getattr(item, "access_group_ids_json", None) if not isinstance(item, dict) else item.get("access_group_ids_json")
        item_group_ids = parse_ids_json(raw_group_ids)

        # Check access_tags_json
        raw_tags = getattr(item, tag_attr, None) if not isinstance(item, dict) else item.get(tag_attr)
        item_tags = set(parse_tags_json(raw_tags))

        # Add group IDs to item_tags for unified matching
        for gid in item_group_ids:
            item_tags.add(str(gid))

        # Empty access scope = globally accessible to all agents
        if not item_tags and not item_group_ids:
            result.append(item)
        # Non-empty scope = requires intersection with agent's effective tags / group IDs
        elif item_tags.intersection(allowed_tags):
            result.append(item)

    return result

