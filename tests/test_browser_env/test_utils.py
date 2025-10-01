from webarena.browser_env.utils import map_url, extract_action_from_response


def test_map_urls_to_local_handles_http_https_and_www_variants() -> None:
    local_to_real = {
        "http://my-local-reddit.com:9999": "http://reddit.com",
    }
    real_to_local = {v: k for k, v in local_to_real.items()}

    # 1. real -> local
    local_url = "goto [http://my-local-reddit.com:9999/r/Showerthoughts]"

    # http
    real_url = "goto [http://reddit.com/r/Showerthoughts]"
    assert map_url(real_url, real_to_local) == local_url

    # https
    real_url = "goto [https://reddit.com/r/Showerthoughts]"
    assert map_url(real_url, real_to_local) == local_url

    # https + www
    real_url = "goto [https://www.reddit.com/r/Showerthoughts]"
    assert map_url(real_url, real_to_local) == local_url

    # preserve query + fragment
    real_url = "goto [https://www.reddit.com/r/Showerthoughts?x=1#frag]"
    local_url = "goto [http://my-local-reddit.com:9999/r/Showerthoughts?x=1#frag]"
    assert map_url(real_url, real_to_local) == local_url

    # 2. local -> real
    real_url = "goto [http://reddit.com/r/Showerthoughts]"

    # http
    local_url = "goto [http://my-local-reddit.com:9999/r/Showerthoughts]"
    assert map_url(local_url, local_to_real) == real_url

    # https
    local_url = "goto [https://my-local-reddit.com:9999/r/Showerthoughts]"
    assert map_url(local_url, local_to_real) == real_url

    # https + www
    local_url = "goto [https://www.my-local-reddit.com:9999/r/Showerthoughts]"

    # preserve query + fragment
    local_url = "goto [http://my-local-reddit.com:9999/r/Showerthoughts?x=1#frag]"
    real_url = "goto [http://reddit.com/r/Showerthoughts?x=1#frag]"
    assert map_url(local_url, local_to_real) == real_url


def test_extract_action_from_response_basic_actions() -> None:
    """Test extraction of basic actions with triple backticks."""
    # Test scroll action (the failing case from the terminal output)
    response = "Let's think step-by-step. I need to scroll down. In summary, the next action I will perform is ```scroll [direction=down]```."
    action = extract_action_from_response(response, "```")
    assert action == "scroll [direction=down]"
    
    # Test click action
    response = "I need to click on the button. In summary, the next action I will perform is ```click [1234]```."
    action = extract_action_from_response(response, "```")
    assert action == "click [1234]"
    
    # Test type action
    response = "I'll type in the search box. In summary, the next action I will perform is ```type [164] [restaurants near CMU] [1]```."
    action = extract_action_from_response(response, "```")
    assert action == "type [164] [restaurants near CMU] [1]"
    
    # Test goto action
    response = "Let's navigate to the page. In summary, the next action I will perform is ```goto [http://example.com]```."
    action = extract_action_from_response(response, "```")
    assert action == "goto [http://example.com]"
    
    # Test stop action
    response = "I found the answer. In summary, the next action I will perform is ```stop [$279.49]```."
    action = extract_action_from_response(response, "```")
    assert action == "stop [$279.49]"


def test_extract_action_from_response_edge_cases() -> None:
    """Test edge cases for action extraction."""
    # No action in response
    response = "This is just text without any action."
    action = extract_action_from_response(response, "```")
    assert action is None
    
    # Empty action
    response = "In summary, the next action I will perform is ``````."
    action = extract_action_from_response(response, "```")
    assert action == ""
    
    # Action with whitespace
    response = "In summary, the next action I will perform is ```  scroll [direction=up]  ```."
    action = extract_action_from_response(response, "```")
    assert action == "scroll [direction=up]"
    
    # Multiple potential actions (should match first)
    response = "First ```click [1]``` then ```scroll [direction=down]```."
    action = extract_action_from_response(response, "```")
    assert action == "click [1]"
    
    # Action with newlines
    response = """Let me think about this.
    In summary, the next action I will perform is ```scroll [direction=down]```.
    This should work."""
    action = extract_action_from_response(response, "```")
    assert action == "scroll [direction=down]"


def test_extract_action_from_response_different_splitters() -> None:
    """Test action extraction with different splitters."""
    # Using different splitter (same splitter for start and end)
    response = "The action is <<<click [123]<<<."
    action = extract_action_from_response(response, "<<<")
    assert action == "click [123]"
    
    # Using single backtick (shouldn't work with triple backtick splitter)
    response = "The action is `click [123]`."
    action = extract_action_from_response(response, "```")
    assert action is None


def test_extract_action_from_response_complex_content() -> None:
    """Test extraction with complex content between splitters."""
    # Action with multiple lines
    response = """The next action is:
    ```
    type [164] [restaurants near CMU] [1]
    ```
    This will search for restaurants."""
    action = extract_action_from_response(response, "```")
    assert action == "type [164] [restaurants near CMU] [1]"
    
    # Action with special characters
    response = "In summary, the next action I will perform is ```type [search] [hello@example.com & test] [0]```."
    action = extract_action_from_response(response, "```")
    assert action == "type [search] [hello@example.com & test] [0]"


def test_extract_action_from_response_realistic_scenarios() -> None:
    """Test with realistic agent responses."""
    # Realistic response matching the terminal output pattern
    response = """Let's think step-by-step. To draft a refund message, I need to locate the "contact us" form on this page or the appropriate section. Currently, I don't see any specific mention of a contact form in the accessibility tree. I should look for a "Contact Us" link or button that might lead to the form. 

In summary, the next action I will perform is ```scroll [direction=down]```."""
    action = extract_action_from_response(response, "```")
    assert action == "scroll [direction=down]"
    
    # Another realistic scenario
    response = """Let's think step-by-step. I can see a search textbox with ID [164]. According to the objective, I need to search for restaurants near CMU. I'll type the search query and press enter.

In summary, the next action I will perform is ```type [164] [restaurants near CMU] [1]```."""
    action = extract_action_from_response(response, "```")
    assert action == "type [164] [restaurants near CMU] [1]"

