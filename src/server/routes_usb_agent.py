import json

from status_led import STATUS_LED
from usb_agent_drive import UsbAgentDrive

from ._http import _PAYLOAD_BIN


class _UsbAgentMixin:
    # Attributes provided by SetupServer.__init__
    _usb_agent_drive: UsbAgentDrive

    # Methods provided by SetupServer / other mixins
    def _is_authorized(self, request) -> bool: ...
    def _has_binary(self) -> bool: ...
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...

    def _usb_agent_state(self) -> dict[str, object]:
        state = self._usb_agent_drive.state()
        state['has_binary'] = self._has_binary()
        if state.get('available') and not state.get('mounted') and not state['has_binary']:
            state['can_mount'] = False
            state['message'] = 'Upload an agent binary before mounting the USB drive.'
        return state

    async def _handle_usb_agent(self, request, writer) -> None:
        if not self._is_authorized(request):
            await self._send_json(
                writer,
                request,
                '401 Unauthorized',
                {'message': 'Sign in required.'},
            )
            return

        if request['method'] == 'GET':
            await self._send_json(writer, request, '200 OK', {'usb_agent': self._usb_agent_state()})
            return

        if request['method'] != 'POST':
            await self._send_json(
                writer,
                request,
                '405 Method Not Allowed',
                {'message': 'Method not allowed.'},
            )
            return

        try:
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
        except ValueError:
            data = {}

        mounted = bool(data.get('mounted'))
        before = self._usb_agent_drive.state()
        self._usb_agent_drive.set_mounted(mounted, agent_path=_PAYLOAD_BIN)
        state = self._usb_agent_state()
        status = '200 OK'
        notice = 'success'
        if mounted and not state.get('mounted'):
            status = '400 Bad Request'
            notice = 'error'

        if state.get('mounted') and not before.get('mounted'):
            await STATUS_LED.show('usb_agent_mounted')
        elif before.get('mounted') and not state.get('mounted'):
            await STATUS_LED.show('usb_agent_unmounted')

        await self._send_json(
            writer,
            request,
            status,
            {
                'message': state.get('message', ''),
                'notice': notice,
                'usb_agent': state,
            },
        )
