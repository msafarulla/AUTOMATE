"""
Tests for the workflow configuration system.
"""
import pytest

from config.workflow_config import (
    ASNItem,
    FlowType,
    OpenUIConfig,
    OpenUIEntry,
    PostStage,
    ReceiveStage,
    LoadingStage,
    TasksStage,
    Workflow,
    WorkflowBuilder,
    create_default_workflows,
    workflows_to_legacy_format,
    flatten_workflows,
)


class TestASNItem:
    """Tests for ASNItem dataclass."""

    def test_default_values(self):
        item = ASNItem(item_name="TEST123")
        assert item.item_name == "TEST123"
        assert item.shipped_qty == 2000
        assert item.received_qty == 0
        assert item.qty_uom == "Unit"

    def test_to_dict(self):
        item = ASNItem(item_name="PART456", shipped_qty=500)
        result = item.to_dict()
        
        assert result["ItemName"] == "PART456"
        assert result["Quantity"]["ShippedQty"] == 500
        assert result["Quantity"]["ReceivedQty"] == 0


class TestOpenUIConfig:
    """Tests for OpenUIConfig."""

    def test_empty_entries(self):
        config = OpenUIConfig()
        assert config.to_dict() == {}

    def test_disabled(self):
        config = OpenUIConfig(
            enabled=False,
            entries=[OpenUIEntry(search_term="test", match_text="Test")]
        )
        assert config.to_dict() == {}

    def test_with_entries(self):
        config = OpenUIConfig(entries=[
            OpenUIEntry(
                search_term="ILPNS",
                match_text="iLPNs (Distribution)",
                fill_ilpn=True,
            )
        ])
        result = config.to_dict()
        
        assert result["enabled"] is True
        assert len(result["entries"]) == 1
        assert result["entries"][0]["search_term"] == "ILPNS"
        assert result["entries"][0]["fill_ilpn"] is True


class TestPostStage:
    """Tests for PostStage."""

    def test_minimal_config(self):
        stage = PostStage(message_type="ASN")
        result = stage.to_dict()
        
        assert result["type"] == "ASN"
        assert result["source"] == "db"
        assert result["enabled"] is True

    def test_with_items(self):
        stage = PostStage(
            message_type="ASN",
            asn_items=[
                ASNItem(item_name="ITEM1", shipped_qty=100),
                ASNItem(item_name="ITEM2", shipped_qty=200),
            ]
        )
        result = stage.to_dict()
        
        assert len(result["asn_items"]) == 2
        assert result["asn_items"][0]["ItemName"] == "ITEM1"


class TestReceiveStage:
    """Tests for ReceiveStage."""

    def test_default_flow(self):
        stage = ReceiveStage()
        result = stage.to_dict()
        
        assert result["flow"] == "HAPPY_PATH"
        assert result["auto_handle_deviation"] is True

    def test_with_open_ui(self):
        stage = ReceiveStage(
            asn="12345678",
            item="TESTITEM",
            quantity=100,
            open_ui=OpenUIConfig(entries=[
                OpenUIEntry(search_term="tasks", match_text="Tasks")
            ])
        )
        result = stage.to_dict()
        
        assert "open_ui" in result
        assert result["open_ui"]["entries"][0]["search_term"] == "tasks"


class TestWorkflowBuilder:
    """Tests for the fluent builder."""

    def test_simple_workflow(self):
        workflow = (
            WorkflowBuilder("test_flow", "inbound")
            .receive(ReceiveStage(asn="123", item="ABC", quantity=10))
            .build()
        )
        
        assert workflow.name == "test_flow"
        assert workflow.bucket == "inbound"
        assert workflow.full_name == "inbound.test_flow"
        assert "receive" in workflow.stages

    def test_multi_stage_workflow(self):
        workflow = (
            WorkflowBuilder("full_flow", "inbound")
            .post(PostStage(message_type="ASN"))
            .receive(ReceiveStage())
            .tasks(TasksStage())
            .build()
        )
        
        assert "post" in workflow.stages
        assert "receive" in workflow.stages
        assert "tasks" in workflow.stages

    def test_outbound_workflow(self):
        workflow = (
            WorkflowBuilder("load_test", "outbound")
            .loading(LoadingStage(
                shipment="SHIP001",
                dock_door="DOOR1",
                bol="BOL123"
            ))
            .build()
        )
        
        assert workflow.bucket == "outbound"
        assert workflow.full_name == "outbound.load_test"
        assert workflow.stages["loading"]["shipment"] == "SHIP001"


class TestWorkflowConversions:
    """Tests for format conversion functions."""

    def test_to_legacy_format(self):
        workflows = [
            WorkflowBuilder("flow1", "inbound").receive(ReceiveStage()).build(),
            WorkflowBuilder("flow2", "inbound").receive(ReceiveStage()).build(),
            WorkflowBuilder("load1", "outbound").loading(
                LoadingStage("S1", "D1", "B1")
            ).build(),
        ]
        
        legacy = workflows_to_legacy_format(workflows)
        
        assert "inbound" in legacy
        assert "outbound" in legacy
        assert "flow1" in legacy["inbound"]
        assert "flow2" in legacy["inbound"]
        assert "load1" in legacy["outbound"]

    def test_flatten_workflows(self):
        workflows = [
            WorkflowBuilder("test1", "bucket1").receive(ReceiveStage()).build(),
            WorkflowBuilder("test2", "bucket2").receive(ReceiveStage()).build(),
        ]
        
        flattened = flatten_workflows(workflows)
        
        assert len(flattened) == 2
        assert flattened[0][0] == "bucket1.test1"
        assert flattened[1][0] == "bucket2.test2"
        assert isinstance(flattened[0][1], dict)


class TestDefaultWorkflows:
    """Tests for the default workflow creation."""

    def test_creates_workflows(self):
        workflows = create_default_workflows()
        
        assert len(workflows) > 0
        assert all(isinstance(w, Workflow) for w in workflows)

    def test_default_workflow_has_stages(self):
        workflows = create_default_workflows()
        
        # Should have at least one workflow with post and receive
        receive_happy = next(
            (w for w in workflows if "HAPPY_PATH" in w.name),
            None
        )
        assert receive_happy is not None
        assert "post" in receive_happy.stages
        assert "receive" in receive_happy.stages