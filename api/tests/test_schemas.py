"""Tests for work-item schemas."""

from app.schemas.work_items import (
    WorkItem,
    WorkItemHierarchy,
    WorkItemType,
)


class TestWorkItemType:
    def test_enum_values(self):
        assert WorkItemType.EPIC == "epic"
        assert WorkItemType.STORY == "story"
        assert WorkItemType.BUG == "bug"
        assert WorkItemType.TASK == "task"


class TestWorkItem:
    def test_minimal_item(self):
        item = WorkItem(type=WorkItemType.EPIC, title="My Epic")
        assert item.type == WorkItemType.EPIC
        assert item.title == "My Epic"
        assert item.description == ""
        assert item.labels == []
        assert item.children == []

    def test_full_item(self):
        child = WorkItem(type=WorkItemType.TASK, title="Sub task")
        item = WorkItem(
            type=WorkItemType.STORY,
            title="User login",
            description="As a user I want to log in",
            labels=["auth", "frontend"],
            children=[child],
        )
        assert len(item.children) == 1
        assert item.children[0].title == "Sub task"

    def test_nested_hierarchy(self):
        task = WorkItem(type=WorkItemType.TASK, title="Write tests")
        story = WorkItem(
            type=WorkItemType.STORY,
            title="Login page",
            children=[task],
        )
        epic = WorkItem(
            type=WorkItemType.EPIC,
            title="Auth system",
            children=[story],
        )
        assert epic.children[0].children[0].title == "Write tests"

    def test_serialization_roundtrip(self):
        item = WorkItem(
            type=WorkItemType.BUG,
            title="Fix crash",
            description="App crashes on startup",
            labels=["bug", "critical"],
        )
        data = item.model_dump()
        restored = WorkItem.model_validate(data)
        assert restored == item

    def test_json_roundtrip(self):
        item = WorkItem(
            type=WorkItemType.EPIC,
            title="Platform",
            children=[
                WorkItem(type=WorkItemType.STORY, title="API"),
            ],
        )
        json_str = item.model_dump_json()
        restored = WorkItem.model_validate_json(json_str)
        assert restored == item


class TestWorkItemHierarchy:
    def test_hierarchy(self):
        hierarchy = WorkItemHierarchy(
            items=[
                WorkItem(type=WorkItemType.EPIC, title="Epic 1"),
                WorkItem(type=WorkItemType.EPIC, title="Epic 2"),
            ]
        )
        assert len(hierarchy.items) == 2
