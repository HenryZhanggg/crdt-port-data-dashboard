"""Media HTTP responses must retain their start message through Streamlit gzip."""
import unittest

from streamlit.web.server.starlette.starlette_gzip_middleware import SelectiveGZipMiddleware


class MediaRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_response_starts_before_its_body(self):
        messages = []
        async def image_app(scope, receive, send):
            await send({'type':'http.response.start','status':200,
                        'headers':[(b'content-type',b'image/jpeg')]})
            await send({'type':'http.response.body','body':b'jpeg-preview'})
        async def receive():
            return {'type':'http.request','body':b''}
        async def send(message):
            messages.append(message)
        middleware = SelectiveGZipMiddleware(image_app)
        for encoding in [b'gzip', b'identity']:
            messages.clear()
            await middleware({'type':'http','path':'/media/photo.jpg',
                              'headers':[(b'accept-encoding',encoding)]},receive,send)
            self.assertEqual([m['type'] for m in messages],
                             ['http.response.start','http.response.body'])
            self.assertEqual(messages[0]['status'],200)
