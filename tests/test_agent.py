from src.agent import SupportAgent


def test_agent_answers_order_status_after_auth(settings):
    agent = SupportAgent(settings)
    agent.chat("Hi, my email is alice@example.com")
    res = agent.chat("What's the status of ORD-1002?")
    assert "shipped" in res.reply.lower()
    assert res.tool_calls[0]["name"] == "get_order_status"
    assert res.authenticated_as == "alice@example.com"


def test_agent_blocks_other_accounts_orders(settings):
    agent = SupportAgent(settings)
    agent.chat("my email is bob@example.com")
    res = agent.chat("status of ORD-1002")  # alice's order
    assert "different account" in res.reply.lower()


def test_agent_return_flow(settings):
    agent = SupportAgent(settings)
    agent.chat("my email is alice@example.com")
    res = agent.chat("I want to return ORD-1001 because it arrived damaged")
    assert res.tool_calls[0]["name"] == "start_return"
    assert "return" in res.reply.lower()


def test_agent_return_policy_faq(settings):
    agent = SupportAgent(settings)
    res = agent.chat("what is your return policy?")
    assert res.tool_calls[0]["name"] == "get_return_policy"
    assert "30 days" in res.reply or "30" in res.reply


def test_agent_list_orders_requires_email(settings):
    agent = SupportAgent(settings)
    res = agent.chat("list my orders")
    assert "email" in res.reply.lower()


def test_agent_memory_persists_identity(settings):
    agent = SupportAgent(settings)
    agent.chat("my email is alice@example.com")
    res = agent.chat("list my orders")  # no email repeated; should use memory
    assert "ORD-1001" in res.reply
