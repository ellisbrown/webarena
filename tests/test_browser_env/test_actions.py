import numpy as np
import pytest

from webarena.browser_env import *


def test_is_equivalent() -> None:
    for action_type in ActionTypes.__members__.values():
        action_a = create_random_action()
        action_b = create_random_action()
        if action_a["action_type"] != action_b["action_type"]:
            assert not is_equivalent(action_a, action_b)
        action_a["action_type"] = action_type
        action_b["action_type"] = action_type
        match action_type:
            case ActionTypes.MOUSE_CLICK | ActionTypes.MOUSE_HOVER:
                if not np.allclose(action_a["coords"], action_b["coords"]):
                    assert not is_equivalent(action_a, action_b)
                    action_a["coords"] = action_b["coords"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.KEYBOARD_TYPE:
                if action_a["text"] != action_b["text"]:
                    assert not is_equivalent(action_a, action_b)
                    action_a["text"] = action_b["text"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.CLICK | ActionTypes.HOVER | ActionTypes.TYPE:
                if action_a["element_id"] and action_b["element_id"]:
                    if action_a["element_id"] != action_b["element_id"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["element_id"] = action_b["element_id"]
                    assert is_equivalent(action_a, action_b)
                elif action_a["element_role"] and action_b["element_role"]:
                    if action_a["element_role"] != action_b["element_role"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["element_role"] = action_b["element_role"]
                    if action_a["element_name"] != action_b["element_name"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["element_name"] = action_b["element_name"]
                    assert is_equivalent(action_a, action_b)
                elif action_a["pw_code"] and action_b["pw_code"]:
                    if action_a["pw_code"] != action_b["pw_code"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["pw_code"] = action_b["pw_code"]
                    assert is_equivalent(action_a, action_b)
                else:
                    action_a["element_id"] = action_b["element_id"]
                    assert is_equivalent(action_a, action_b)
            case ActionTypes.GOTO_URL:
                if action_a["url"] != action_b["url"]:
                    assert not is_equivalent(action_a, action_b)
                    action_a["url"] = action_b["url"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.PAGE_FOCUS:
                if action_a["page_number"] != action_b["page_number"]:
                    assert not is_equivalent(action_a, action_b)
                    action_a["page_number"] = action_b["page_number"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.SCROLL:
                da = "up" if "up" in action_a["direction"] else "down"
                db = "up" if "up" in action_b["direction"] else "down"
                if da != db:
                    assert not is_equivalent(action_a, action_b)
                    action_a["direction"] = action_b["direction"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.KEY_PRESS:
                if action_a["key_comb"] != action_b["key_comb"]:
                    assert not is_equivalent(action_a, action_b)
                    action_a["key_comb"] = action_b["key_comb"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.CHECK | ActionTypes.SELECT_OPTION:
                if action_a["pw_code"] != action_b["pw_code"]:
                    assert not is_equivalent(action_a, action_b)
                    action_a["pw_code"] = action_b["pw_code"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.STOP:
                if action_a["answer"] != action_b["answer"]:
                    assert not is_equivalent(action_a, action_b)
                    action_a["answer"] = action_b["answer"]
                assert is_equivalent(action_a, action_b)
            case ActionTypes.CLEAR:
                if action_a["element_id"] and action_b["element_id"]:
                    if action_a["element_id"] != action_b["element_id"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["element_id"] = action_b["element_id"]
                    assert is_equivalent(action_a, action_b)
                elif action_a["element_role"] and action_b["element_role"]:
                    if action_a["element_role"] != action_b["element_role"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["element_role"] = action_b["element_role"]
                    if action_a["element_name"] != action_b["element_name"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["element_name"] = action_b["element_name"]
                    assert is_equivalent(action_a, action_b)
                elif action_a["pw_code"] and action_b["pw_code"]:
                    if action_a["pw_code"] != action_b["pw_code"]:
                        assert not is_equivalent(action_a, action_b)
                        action_a["pw_code"] = action_b["pw_code"]
                    assert is_equivalent(action_a, action_b)
                else:
                    action_a["element_id"] = action_b["element_id"]
                    assert is_equivalent(action_a, action_b)
            case _:
                assert is_equivalent(action_a, action_b)


def test_action2create_function() -> None:
    for _ in range(1000):
        action = create_random_action()
        create_function = action2create_function(action)
        assert is_equivalent(action, eval(create_function))


def test_create_id_based_action_basic_parsing() -> None:
    # click
    assert is_equivalent(
        create_id_based_action("click [123]"), create_click_action(element_id="123")
    )

    # hover
    assert is_equivalent(
        create_id_based_action("hover [42]"), create_hover_action(element_id="42")
    )

    # press key combination (normalize mappings and case)
    assert is_equivalent(
        create_id_based_action("press [Ctrl+v]"),
        create_key_press_action(key_comb="Control+v"),
    )

    # press with spaces around plus should still work
    assert is_equivalent(
        create_id_based_action("press [Ctrl + v]"),
        create_key_press_action(key_comb="Control+v"),
    )

    # scroll variants
    assert is_equivalent(
        create_id_based_action("scroll [down]"),
        create_scroll_action(direction="down"),
    )
    assert is_equivalent(
        create_id_based_action("scroll down"),
        create_scroll_action(direction="down"),
    )
    assert is_equivalent(
        create_id_based_action("scroll [up]"), create_scroll_action(direction="up")
    )

    # navigation and tabs
    assert is_equivalent(
        create_id_based_action("goto [http://example.com]"),
        create_goto_url_action(url="http://example.com"),
    )
    assert is_equivalent(create_id_based_action("new_tab"), create_new_tab_action())
    assert is_equivalent(create_id_based_action("go_back"), create_go_back_action())
    assert is_equivalent(
        create_id_based_action("go_forward"), create_go_forward_action()
    )
    assert is_equivalent(
        create_id_based_action("tab_focus [2]"), create_page_focus_action(2)
    )
    assert is_equivalent(
        create_id_based_action("close_tab"), create_page_close_action()
    )

    # stop with and without answer
    assert is_equivalent(
        create_id_based_action("stop [done]"), create_stop_action("done")
    )
    assert is_equivalent(create_id_based_action("stop"), create_stop_action(""))

    # type
    # > default adds Enter (equivalent by element_id, and text includes newline)
    parsed = create_id_based_action("type [530] [Pittsburgh Airport]")
    expected = create_type_action(text="Pittsburgh Airport\n", element_id="530")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]

    # explicit numeric flags
    parsed = create_id_based_action("type [530] [Pittsburgh Airport] [1]")
    expected = create_type_action(text="Pittsburgh Airport\n", element_id="530")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]

    parsed = create_id_based_action("type [530] [Pittsburgh Airport] [0]")
    expected = create_type_action(text="Pittsburgh Airport", element_id="530")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]


def test_create_id_based_action_kwargs() -> None:
    """Test kwarg syntax [key=value] for all action types that support parameters."""
    
    # ==================== TYPE ACTION KWARGS ====================
    # kwarg variants for press_enter_after
    parsed = create_id_based_action(
        "type [530] [Pittsburgh Airport] [press_enter_after=0]"
    )
    expected = create_type_action(text="Pittsburgh Airport", element_id="530")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]

    parsed = create_id_based_action(
        "type [530] [Pittsburgh Airport] [press_enter_after=1]"
    )
    expected = create_type_action(text="Pittsburgh Airport\n", element_id="530")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]

    # type with spaces around equals
    parsed = create_id_based_action(
        "type [530] [Pittsburgh Airport] [press_enter_after = 0]"
    )
    expected = create_type_action(text="Pittsburgh Airport", element_id="530")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]

    # ==================== SCROLL ACTION KWARGS ====================
    # scroll [direction=up/down]
    parsed = create_id_based_action("scroll [direction=up]")
    expected = create_scroll_action(direction="up")
    assert is_equivalent(parsed, expected)
    assert parsed["direction"] == expected["direction"]
    
    parsed = create_id_based_action("scroll [direction=down]")
    expected = create_scroll_action(direction="down")
    assert is_equivalent(parsed, expected)
    assert parsed["direction"] == expected["direction"]

    # scroll with spaces around equals
    parsed = create_id_based_action("scroll [direction = up]")
    expected = create_scroll_action(direction="up")
    assert is_equivalent(parsed, expected)
    assert parsed["direction"] == expected["direction"]

    # invalid direction should raise error
    with pytest.raises(ActionParsingError):
        create_id_based_action("scroll [direction=left]")

    # ==================== CLICK ACTION KWARGS ====================
    # click [element_id=123]
    parsed = create_id_based_action("click [element_id=123]")
    expected = create_click_action(element_id="123")
    assert is_equivalent(parsed, expected)
    assert parsed["element_id"] == expected["element_id"]

    # click with spaces around equals
    parsed = create_id_based_action("click [element_id = 456]")
    expected = create_click_action(element_id="456")
    assert is_equivalent(parsed, expected)
    assert parsed["element_id"] == expected["element_id"]

    # ==================== HOVER ACTION KWARGS ====================
    # hover [element_id=42]
    parsed = create_id_based_action("hover [element_id=42]")
    expected = create_hover_action(element_id="42")
    assert is_equivalent(parsed, expected)
    assert parsed["element_id"] == expected["element_id"]

    # hover with spaces around equals
    parsed = create_id_based_action("hover [element_id = 789]")
    expected = create_hover_action(element_id="789")
    assert is_equivalent(parsed, expected)
    assert parsed["element_id"] == expected["element_id"]

    # ==================== PRESS ACTION KWARGS ====================
    # press [key_comb=Ctrl+v]
    parsed = create_id_based_action("press [key_comb=Ctrl+v]")
    expected = create_key_press_action(key_comb="Control+v")
    assert is_equivalent(parsed, expected)
    
    # press with spaces around equals
    parsed = create_id_based_action("press [key_comb = Escape]")
    expected = create_key_press_action(key_comb="Escape")
    assert is_equivalent(parsed, expected)

    # ==================== GOTO ACTION KWARGS ====================
    # goto [url=http://example.com]
    parsed = create_id_based_action("goto [url=http://example.com]")
    expected = create_goto_url_action(url="http://example.com")
    assert is_equivalent(parsed, expected)
    assert parsed["url"] == expected["url"]

    # goto with spaces around equals
    parsed = create_id_based_action("goto [url = https://github.com]")
    expected = create_goto_url_action(url="https://github.com")
    assert is_equivalent(parsed, expected)
    assert parsed["url"] == expected["url"]

    # ==================== TAB_FOCUS ACTION KWARGS ====================
    # tab_focus [page_number=2]
    parsed = create_id_based_action("tab_focus [page_number=2]")
    expected = create_page_focus_action(2)
    assert is_equivalent(parsed, expected)
    assert parsed["page_number"] == expected["page_number"]

    # tab_focus with spaces around equals
    parsed = create_id_based_action("tab_focus [page_number = 3]")
    expected = create_page_focus_action(3)
    assert is_equivalent(parsed, expected)
    assert parsed["page_number"] == expected["page_number"]

    # ==================== STOP ACTION KWARGS ====================
    # stop [answer=done]
    parsed = create_id_based_action("stop [answer=done]")
    expected = create_stop_action("done")
    assert is_equivalent(parsed, expected)
    assert parsed["answer"] == expected["answer"]

    # stop with spaces around equals
    parsed = create_id_based_action("stop [answer = completed]")
    expected = create_stop_action("completed")
    assert is_equivalent(parsed, expected)
    assert parsed["answer"] == expected["answer"]

    # ==================== MIXED KWARGS WITH VARIOUS SPACING ====================
    # Test that our regex handles various spacing patterns correctly
    test_cases = [
        ("click [element_id=123]", "123"),
        ("click [element_id =123]", "123"),
        ("click [element_id= 123]", "123"),
        ("click [element_id = 123]", "123"),
        ("click [element_id  =  123]", "123"),
    ]
    
    for action_str, expected_id in test_cases:
        parsed = create_id_based_action(action_str)
        expected = create_click_action(element_id=expected_id)
        assert is_equivalent(parsed, expected)
        assert parsed["element_id"] == expected["element_id"]


def test_preprocess_action_kwargs() -> None:
    """Test the kwarg preprocessing function directly."""
    
    # Test basic kwarg conversion
    assert preprocess_action_kwargs("scroll [direction=up]") == "scroll [up]"
    assert preprocess_action_kwargs("scroll [direction=down]") == "scroll [down]"
    assert preprocess_action_kwargs("click [element_id=123]") == "click [123]"
    assert preprocess_action_kwargs("hover [element_id=456]") == "hover [456]"
    
    # Test with spaces around equals
    assert preprocess_action_kwargs("scroll [direction = up]") == "scroll [up]"
    assert preprocess_action_kwargs("click [element_id =123]") == "click [123]"
    assert preprocess_action_kwargs("hover [element_id= 456]") == "hover [456]"
    assert preprocess_action_kwargs("type [530] [text] [press_enter_after = 1]") == "type [530] [text] [1]"
    
    # Test various spacing patterns
    assert preprocess_action_kwargs("click [element_id  =  123]") == "click [123]"
    assert preprocess_action_kwargs("press [key_comb=Ctrl+v]") == "press [Ctrl+v]"
    assert preprocess_action_kwargs("goto [url=http://example.com]") == "goto [http://example.com]"
    
    # Test no change for non-kwarg patterns
    assert preprocess_action_kwargs("scroll [up]") == "scroll [up]"
    assert preprocess_action_kwargs("click [123]") == "click [123]"
    assert preprocess_action_kwargs("type [530] [text] [1]") == "type [530] [text] [1]"
    
    # Test multiple kwargs in one string
    assert preprocess_action_kwargs("type [element_id=530] [text=hello] [press_enter_after=1]") == "type [530] [hello] [1]"
    
    # Test kwargs with complex values containing special characters
    assert preprocess_action_kwargs("goto [url=https://example.com/path?param=value]") == "goto [https://example.com/path?param=value]"
    assert preprocess_action_kwargs("press [key_comb=Ctrl+Shift+Tab]") == "press [Ctrl+Shift+Tab]"
    
    # Test edge cases
    assert preprocess_action_kwargs("action [param=]") == "action []"  # empty value
    assert preprocess_action_kwargs("action [param=value with spaces]") == "action [value with spaces]"
    
    # Test that non-bracketed content is unchanged
    assert preprocess_action_kwargs("scroll up") == "scroll up"
    assert preprocess_action_kwargs("new_tab") == "new_tab"


def test_create_id_based_action_additional_tolerances() -> None:
    # extra whitespace around tokens
    assert is_equivalent(
        create_id_based_action("  click   [123]  "),
        create_click_action(element_id="123"),
    )

    # scroll without brackets (up) and with mixed spacing
    assert is_equivalent(
        create_id_based_action("scroll up"), create_scroll_action(direction="up")
    )

    # press synonyms and casing variations
    assert is_equivalent(
        create_id_based_action("press [CTRL+V]"),
        create_key_press_action(key_comb="Control+v"),
    )
    assert is_equivalent(
        create_id_based_action("press [cmd + v]"),
        create_key_press_action(key_comb="Meta+v"),
    )
    assert is_equivalent(
        create_id_based_action("press [esc]"),
        create_key_press_action(key_comb="Escape"),
    )
    assert is_equivalent(
        create_id_based_action("press [PgDn]"),
        create_key_press_action(key_comb="PageDown"),
    )
    assert is_equivalent(
        create_id_based_action("press [Meta+a]"),
        create_key_press_action(key_comb="Meta+a"),
    )

    # type text including plus signs should parse fine
    parsed = create_id_based_action("type [12] [C++] [0]")
    expected = create_type_action(text="C++", element_id="12")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]

    # type with empty content and explicit enter flag
    parsed = create_id_based_action("type [7] [] [1]")
    expected = create_type_action(text="\n", element_id="7")
    assert is_equivalent(parsed, expected)
    assert parsed["text"] == expected["text"]
