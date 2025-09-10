from iam.authz import authorize


def test_authorize_basic():
    subject = {"roles": ["viewer"]}
    res = authorize(subject, action="read", resource_type="event", resource_tenant="t1")
    assert res.allowed
