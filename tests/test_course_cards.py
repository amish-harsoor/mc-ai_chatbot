"""Tests for clean course card markdown and stream normalization."""

from src.chatbot.course_cards import (
    format_course_card_markdown,
    normalize_course_markdown,
)


def test_format_card_title_and_facts_only():
    card = format_course_card_markdown(
        course_id="4606",
        title="Introduction to Data Visualization",
        description="This should not appear.",
        duration="2 Days",
        credits="CLP: 16 | CPE: 16",
        price="$1409.00",
        level="Intermediate",
        why="Should not appear either.",
    )
    assert card == (
        "**Introduction to Data Visualization**\n"
        "\n"
        "**Duration:** 2 Days\n"
        "\n"
        "**Credits:** CLP: 16 | CPE: 16\n"
        "\n"
        "**Cost:** $1409.00\n"
        "\n"
        "[Register Now](https://www.managementconcepts.com/product/4606)"
    )
    assert "Level:" not in card
    assert "This should not appear" not in card
    assert "Should not appear either" not in card
    assert "**4606" not in card


def test_format_card_omits_missing_facts():
    card = format_course_card_markdown(
        course_id="1001",
        title="IT Acquisition",
        duration="3 Days",
    )
    assert card == (
        "**IT Acquisition**\n"
        "\n"
        "**Duration:** 3 Days\n"
        "\n"
        "[Register Now](https://www.managementconcepts.com/product/1001)"
    )


def test_normalize_demotes_title_link_and_adds_register_once():
    raw = (
        "**4606** [Introduction to Data Visualization]"
        "(https://www.managementconcepts.com/product/4606)\n"
        "Duration: 2 Days"
    )
    cleaned = normalize_course_markdown(raw)
    assert "[Introduction to Data Visualization](" not in cleaned
    assert "Introduction to Data Visualization" in cleaned
    assert cleaned.count("[Register Now](") == 1
    assert "product/4606" in cleaned


def test_normalize_does_not_duplicate_existing_register():
    raw = (
        "**4606 — Introduction to Data Visualization**\n"
        "Duration: 2 Days\n"
        "[Register Now](https://www.managementconcepts.com/product/4606)"
    )
    cleaned = normalize_course_markdown(raw)
    assert cleaned.count("[Register Now](") == 1


def test_normalize_handles_multiple_courses():
    raw = (
        "**1001** [IT Acquisition](https://www.managementconcepts.com/product/1001)\n"
        "Duration: 3 Days\n\n"
        "**4606** [Data Viz](https://www.managementconcepts.com/product/4606)\n"
        "Duration: 2 Days"
    )
    cleaned = normalize_course_markdown(raw)
    assert cleaned.count("[Register Now](") == 2
    assert "[IT Acquisition](" not in cleaned
    assert "[Data Viz](" not in cleaned
