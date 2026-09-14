import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from app import agent
from app.models import CreativeBrief, Inquiry, InquiryAnalysis, Moodboard, MoodboardTile


class ToolCallingAgent:
    def __init__(self, **kwargs):
        self.tools = {item.tool_name: item for item in kwargs["tools"]}

    def __call__(self, _prompt):
        for name in self.tools:
            self.tools[name]._tool_func()
        if "read_intake_context" in self.tools:
            return '{"status":"ready_for_planning","summary":"Ready","concept_name":"Portrait","missing_information":[],"questions":[]}'
        return "complete"


class AgentCoordinationTests(unittest.TestCase):
    def setUp(self):
        self.inquiry = Inquiry(client_name="Client", client_email="client@example.com", message="Portrait", availability_windows=["09:00–12:00"])

    def test_intake_calls_context_followups_and_specialist(self):
        with patch.object(agent, "BEDROCK_API_KEY", "test"), patch.object(agent, "OpenAIModel"), patch.object(agent, "Agent", ToolCallingAgent):
            result = agent.coordinate_inquiry_intake(42, self.inquiry, [{"id": 1, "answers": "Ten images"}])
        self.assertTrue(result["agent_used_tools"])
        self.assertEqual(result["analysis"].summary, "Ready")
        self.assertEqual(len(result["activity"]), 3)

    def test_creative_tools_persist_brief_before_moodboard(self):
        brief = CreativeBrief(concept_name="Portrait", creative_summary="Soft portrait", shoot_type="portrait", location_direction="park", lighting_direction="soft", posing_direction="natural", wardrobe_direction="casual", budget_notes="within budget")
        moodboard = Moodboard(title="Portrait board", creative_direction="soft", tiles=[MoodboardTile(title="Hero", visual_prompt="portrait", caption="hero", styling_notes="soft")])
        saved = []
        with patch.object(agent, "BEDROCK_API_KEY", "test"), patch.object(agent, "OpenAIModel"), patch.object(agent, "Agent", ToolCallingAgent), patch.object(agent, "create_creative_brief", return_value=brief), patch.object(agent, "create_moodboard", return_value=moodboard):
            result = agent.coordinate_creative_direction(42, self.inquiry, [], lambda item: saved.append(("brief", item)), lambda item: saved.append(("moodboard", item)))
        self.assertEqual([name for name, _ in saved], ["brief", "moodboard"])
        self.assertTrue(result["agent_used_tools"])
        self.assertEqual(len(result["activity"]), 4)

    def test_agent_cannot_claim_success_without_tools(self):
        class NoToolAgent:
            def __init__(self, **_kwargs):
                pass
            def __call__(self, _prompt):
                return "done"
        with patch.object(agent, "BEDROCK_API_KEY", "test"), patch.object(agent, "OpenAIModel"), patch.object(agent, "Agent", NoToolAgent):
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                agent.coordinate_inquiry_intake(42, self.inquiry, [])

    def test_structured_agentcore_result_does_not_require_tool_use(self):
        remote = {
            "result": {"status": "COMPLETE", "summary": "Ready"},
            "agent_used_tools": False,
            "agent_execution": "agentcore",
        }
        with (
            patch.dict(agent.os.environ, {"SHOTCRAFT_AGENTCORE_ENABLED": "true"}),
            patch.object(agent, "_invoke_agentcore", return_value=remote),
            patch.object(agent, "Agent") as local_agent,
        ):
            result = agent._complete("system", "prompt", "model")
        self.assertEqual(result, '{"status": "COMPLETE", "summary": "Ready"}')
        local_agent.assert_not_called()

    def test_agentcore_decodes_utf8_character_split_across_stream_chunks(self):
        expected = {"agent_execution": "agentcore", "result": {"summary": "Seattle 📷 shoot"}}
        body = agent.json.dumps(expected, ensure_ascii=False).encode("utf-8")
        split = body.index("📷".encode("utf-8")) + 1
        with (
            patch.dict(agent.os.environ, {"SHOTCRAFT_AGENTCORE_ENABLED": "true", "SHOTCRAFT_AGENTCORE_RUNTIME_ARN": "test-runtime"}),
            patch("boto3.client") as boto_client,
        ):
            boto_client.return_value.invoke_agent_runtime.return_value = {
                "response": [{"chunk": body[:split]}, {"chunk": body[split:]}],
            }
            result = agent._invoke_agentcore({"operation": "structured_completion"})
        self.assertEqual(result, expected)

    def test_agentcore_scheduling_response_identifies_remote_execution(self):
        runtime = Path(__file__).resolve().parents[1] / "agentcore-runtime/shotcraftagent/app/ShotcraftScheduling/main.py"
        module = ast.parse(runtime.read_text())
        entrypoint = next(node for node in module.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "invoke")
        scheduling_returns = [
            node.value for node in ast.walk(entrypoint)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
            and any(isinstance(key, ast.Constant) and key.value == "decision" for key in node.value.keys)
        ]
        self.assertEqual(len(scheduling_returns), 1)
        response = scheduling_returns[0]
        fields = {key.value: value for key, value in zip(response.keys, response.values) if isinstance(key, ast.Constant)}
        self.assertEqual(fields["agent_execution"].value, "agentcore")


if __name__ == "__main__":
    unittest.main()
