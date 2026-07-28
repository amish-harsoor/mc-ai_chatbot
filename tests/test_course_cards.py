"""Tests for clean course card markdown and stream normalization."""

from src.chatbot.course_cards import (
    format_course_card_markdown,
    normalize_course_markdown,
)


def test_format_card_single_register_link_plain_title():
    card = format_course_card_markdown(
        course_id="4606",
        title="Introduction to Data Visualization",
        duration="2 Days",
        level="Intermediate",
        price="$1409.00",
    )
    assert card == (
        "**4606 — Introduction to Data Visualization**\n"
        "Duration: 2 Days\n"
        "Level: Intermediate\n"
        "Cost: $1409.00\n"
        "[Register Now](https://www.managementconcepts.com/product/4606)"
    )
    assert "[Introduction to Data Visualization](" not in card


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
