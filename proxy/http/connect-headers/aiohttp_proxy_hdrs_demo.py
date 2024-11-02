#!/usr/bin/env python3
"""
Demontration of how to read HTTP CONNECT proxy responce headers using aiohttp v3.10.10
"""
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Tuple,
)
import attr
from http import HTTPStatus

from aiohttp import hdrs, TCPConnector, ClientSession
from aiohttp.connector import Connection
from aiohttp.client_exceptions import ClientProxyConnectionError, ClientHttpProxyError
from aiohttp.client_proto import ResponseHandler
from aiohttp.client_reqrep import ClientRequest
import asyncio
import pprint
pp = pprint.PrettyPrinter(indent=4).pprint

if TYPE_CHECKING:
    from aiohttp.client import ClientTimeout
    from aiohttp.tracing import Trace


PROXY_URL = "http://package-<PKG-ID>:<AUTH-KEY>@proxy.soax.com:5000"
IP_CHECKER_URL = "https://checker.soax.com/api/ipinfo"
HTTP_HRS_TO_PROXY = ('Respond-With', 'uid,ip,country,region,city,isp,asn')


class ProxyRespHdrCapturingConnector(TCPConnector):
    """ The only thing we need is just to copy the proxy response header
        inside `_create_proxy_connection` method.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.proxy_resp_hdrs = {}

    async def _create_proxy_connection(
        self, req: ClientRequest, traces: List["Trace"], timeout: "ClientTimeout"
    ) -> Tuple[asyncio.BaseTransport, ResponseHandler]:
        self._fail_on_no_start_tls(req)
        runtime_has_start_tls = self._loop_supports_start_tls()

        headers: Dict[str, str] = {}
        if req.proxy_headers is not None:
            headers = req.proxy_headers  # type: ignore[assignment]
        headers[hdrs.HOST] = req.headers[hdrs.HOST]

        url = req.proxy
        assert url is not None
        proxy_req = ClientRequest(
            hdrs.METH_GET,
            url,
            headers=headers,
            auth=req.proxy_auth,
            loop=self._loop,
            ssl=req.ssl,
        )

        # create connection to proxy server
        transport, proto = await self._create_direct_connection(
            proxy_req, [], timeout, client_error=ClientProxyConnectionError
        )

        # Many HTTP proxies has buggy keepalive support.  Let's not
        # reuse connection but close it after processing every
        # response.
        proto.force_close()

        auth = proxy_req.headers.pop(hdrs.AUTHORIZATION, None)
        if auth is not None:
            if not req.is_ssl():
                req.headers[hdrs.PROXY_AUTHORIZATION] = auth
            else:
                proxy_req.headers[hdrs.PROXY_AUTHORIZATION] = auth

        if req.is_ssl():
            if runtime_has_start_tls:
                self._warn_about_tls_in_tls(transport, req)

            # For HTTPS requests over HTTP proxy
            # we must notify proxy to tunnel connection
            # so we send CONNECT command:
            #   CONNECT www.python.org:443 HTTP/1.1
            #   Host: www.python.org
            #
            # next we must do TLS handshake and so on
            # to do this we must wrap raw socket into secure one
            # asyncio handles this perfectly
            proxy_req.method = hdrs.METH_CONNECT
            proxy_req.url = req.url
            key = attr.evolve(
                req.connection_key, proxy=None, proxy_auth=None, proxy_headers_hash=None
            )
            conn = Connection(self, key, proto, self._loop)
            proxy_resp = await proxy_req.send(conn)
            try:
                protocol = conn._protocol
                assert protocol is not None

                # read_until_eof=True will ensure the connection isn't closed
                # once the response is received and processed allowing
                # START_TLS to work on the connection below.
                protocol.set_response_params(
                    read_until_eof=runtime_has_start_tls,
                    timeout_ceil_threshold=self._timeout_ceil_threshold,
                )
                resp = await proxy_resp.start(conn)
                self.proxy_resp_hdrs = resp.headers
            except BaseException:
                proxy_resp.close()
                conn.close()
                raise
            else:
                conn._protocol = None
                conn._transport = None
                try:
                    if resp.status != 200:
                        message = resp.reason
                        if message is None:
                            message = HTTPStatus(resp.status).phrase
                        raise ClientHttpProxyError(
                            proxy_resp.request_info,
                            resp.history,
                            status=resp.status,
                            message=message,
                            headers=resp.headers,
                        )
                    if not runtime_has_start_tls:
                        rawsock = transport.get_extra_info("socket", default=None)
                        if rawsock is None:
                            raise RuntimeError(
                                "Transport does not expose socket instance"
                            )
                        # Duplicate the socket, so now we can close proxy transport
                        rawsock = rawsock.dup()
                except BaseException:
                    # It shouldn't be closed in `finally` because it's fed to
                    # `loop.start_tls()` and the docs say not to touch it after
                    # passing there.
                    transport.close()
                    raise
                finally:
                    if not runtime_has_start_tls:
                        transport.close()

                if not runtime_has_start_tls:
                    # HTTP proxy with support for upgrade to HTTPS
                    sslcontext = self._get_ssl_context(req)
                    return await self._wrap_existing_connection(
                        self._factory,
                        timeout=timeout,
                        ssl=sslcontext,
                        sock=rawsock,
                        server_hostname=req.host,
                        req=req,
                    )

                return await self._start_tls_connection(
                    # Access the old transport for the last time before it's
                    # closed and forgotten forever:
                    transport,
                    req=req,
                    timeout=timeout,
                )
            finally:
                proxy_resp.close()

        return transport, proto


async def main():
    connector = ProxyRespHdrCapturingConnector(ssl=False)
    async with ClientSession(connector=connector) as session:
        async with session.get(IP_CHECKER_URL, proxy=PROXY_URL, proxy_headers=[HTTP_HRS_TO_PROXY]) as resp:
            tgt_payload = await resp.json()

            print('-' * 80, '\nTarget\n', '-' * 80, sep='')
            print('*Headres*')
            pp(dict(resp.headers))
            print('*Payload*')
            pp(tgt_payload)

    print('\n', '-' * 80, '\nProxy\n', '-' * 80, sep='')
    print('*Headres*')
    pp(dict(connector.proxy_resp_hdrs))


if __name__ == '__main__':
    asyncio.run(main())
