import httpx
import respx

from cinode import Cinode


def test_whoami_is_unversioned(client: Cinode, api: respx.MockRouter) -> None:
    route = api.get("/_whoami").mock(
        return_value=httpx.Response(200, json={"companyId": 99, "companyUserId": 1001})
    )
    whoami = client.whoami()
    assert route.called
    assert (whoami.company_id, whoami.user_id) == (99, 1001)
