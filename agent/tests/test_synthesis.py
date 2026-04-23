"""Tests for the Synthesis Agent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from agent.nodes import synthesis
from agent.schemas import synthesis as synthesis_schemas


@pytest.fixture
def mock_gateway():
    """Provide a mock ModelGateway."""
    gateway = MagicMock()
    synthesis.set_gateway(gateway)
    yield gateway


@pytest.mark.asyncio
async def test_synthesis_node_success(mock_gateway):
    """Test successful synthesis with valid input."""
    
    # Mock LLM response
    mock_response = json.dumps({
        "summary": "The three cards reveal a path of transformation and growth.",
        "action_advice": "Take concrete steps toward change and trust your instincts.",
        "reflection_question": "How will you honor this transition in your life?"
    })
    mock_gateway.run.return_value = mock_response
    
    # Create input
    synthesis_input = synthesis_schemas.SynthesisInput(
        normalized_question="How can I embrace change?",
        card_interpretations=[
            "Card 1: You have the power to create change.",
            "Card 2: The challenge is letting go of old patterns.",
            "Card 3: Growth and new beginnings await you."
        ],
        locale="en"
    )
    
    # Execute
    output = await synthesis.synthesis_node(synthesis_input)
    
    # Verify output structure
    assert isinstance(output, synthesis_schemas.SynthesisOutput)
    assert output.summary
    assert output.action_advice
    assert output.reflection_question
    assert "transformation" in output.summary.lower()


@pytest.mark.asyncio
async def test_synthesis_node_with_markdown_fence(mock_gateway):
    """Test parsing JSON with markdown code fence."""
    
    # Mock LLM response with markdown fence
    mock_response = """```json
{
  "summary": "A journey of discovery and healing.",
  "action_advice": "Listen to your inner wisdom.",
  "reflection_question": "What does healing mean to you?"
}
```"""
    mock_gateway.run.return_value = mock_response
    
    synthesis_input = synthesis_schemas.SynthesisInput(
        normalized_question="How can I heal?",
        card_interpretations=["Card 1", "Card 2", "Card 3"],
        locale="en"
    )
    
    output = await synthesis.synthesis_node(synthesis_input)
    
    assert output.summary == "A journey of discovery and healing."
    assert output.action_advice == "Listen to your inner wisdom."
    assert output.reflection_question == "What does healing mean to you?"


@pytest.mark.asyncio
async def test_synthesis_node_gateway_failure(mock_gateway):
    """Test fallback when gateway fails."""
    
    # Mock gateway exception
    mock_gateway.run.side_effect = Exception("Connection error")
    
    synthesis_input = synthesis_schemas.SynthesisInput(
        normalized_question="Test question?",
        card_interpretations=["Card 1", "Card 2", "Card 3"],
        locale="en"
    )
    
    output = await synthesis.synthesis_node(synthesis_input)
    
    # Should return fallback output
    assert isinstance(output, synthesis_schemas.SynthesisOutput)
    assert output.summary  # Has fallback content
    assert "Please take time" in output.summary


@pytest.mark.asyncio
async def test_synthesis_node_invalid_json(mock_gateway):
    """Test fallback when JSON is invalid."""
    
    # Mock invalid JSON response
    mock_gateway.run.return_value = "This is not JSON {invalid"
    
    synthesis_input = synthesis_schemas.SynthesisInput(
        normalized_question="Test question?",
        card_interpretations=["Card 1", "Card 2", "Card 3"],
        locale="en"
    )
    
    output = await synthesis.synthesis_node(synthesis_input)
    
    # Should return fallback output
    assert isinstance(output, synthesis_schemas.SynthesisOutput)
    assert output.summary


def test_extract_json_no_fence():
    """Test _extract_json with raw JSON (no fence)."""
    
    raw = '{"summary": "test", "action_advice": "do this", "reflection_question": "why?"}'
    result = synthesis._extract_json(raw)
    
    assert result == raw


def test_extract_json_with_fence():
    """Test _extract_json with markdown fence."""
    
    raw = """```json
{"summary": "test"}
```"""
    
    result = synthesis._extract_json(raw)
    
    # Should remove markdown fence
    assert "```" not in result
    assert "summary" in result


def test_create_fallback_output():
    """Test fallback output generation."""
    
    output = synthesis._create_fallback_output()
    
    assert isinstance(output, synthesis_schemas.SynthesisOutput)
    assert output.summary
    assert output.action_advice
    assert output.reflection_question
    assert "Please take time" in output.summary


def test_build_user_message():
    """Test user message formatting."""
    
    synthesis_input = synthesis_schemas.SynthesisInput(
        normalized_question="What is my purpose?",
        card_interpretations=[
            "Past: You have hidden potential.",
            "Present: You are discovering your gifts.",
            "Future: You will shine brightly."
        ],
        locale="zh-CN"
    )
    
    message = synthesis._build_user_message(synthesis_input)
    
    # Verify message structure
    assert "User's Question" in message
    assert "What is my purpose?" in message
    assert "Card Interpretations" in message
    assert "Card 1" in message
    assert "Card 2" in message
    assert "Card 3" in message
    assert "zh-CN" in message
