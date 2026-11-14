"""Local, attributed Liverpool reference photos and an optional official film."""
from datetime import date
from html import escape
import json
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st


_ROOT = Path(__file__).resolve().parent
_SOURCE_HOSTS = {'commons.wikimedia.org', 'creativecommons.org', 'www.peelports.com', 'www.youtube.com'}


def _load_manifest():
    return json.loads((_ROOT / 'data' / 'public_media.json').read_text(encoding='utf-8'))


def _safe_url(value):
    try:
        parsed = urlparse(value or '')
        valid = parsed.scheme == 'https' and parsed.hostname in _SOURCE_HOSTS and parsed.port in (None, 443) and not parsed.username and not parsed.password
    except ValueError:
        return None
    return value if valid else None


def _credit_html(photo):
    parts = [escape(photo['attribution'])]
    for label, target in [(photo['license'], photo['license_url']), ('Source', photo['source_page'])]:
        url = _safe_url(target)
        if url:
            parts.append('<a href="' + escape(url, quote=True) + '" target="_blank" rel="noopener noreferrer">' + escape(label) + '</a>')
    return ' · '.join(parts)


def render_public_media():
    media = _load_manifest()
    with st.container(border=True, key='daily_public_media'):
        st.markdown('**From the waterfront**')
        photos_tab, video_tab = st.tabs(['Photos', 'Video'], key='public_media_tab', on_change='rerun')
        if photos_tab.open:
            with photos_tab:
                for column, photo in zip(st.columns(2, gap='small'), media['photos']):
                    with column:
                        st.image(str(_ROOT / photo['local_path']), caption=photo['title'], width='stretch')
                        st.caption('Historical photo · ' + date.fromisoformat(photo['captured_at']).strftime('%d %b %Y'))
                        st.caption(_credit_html(photo), unsafe_allow_html=True)
                st.caption('Reduced-resolution previews; colours unchanged. Adaptations shared under CC BY-SA 4.0.')
        if video_tab.open:
            with video_tab:
                video = media['video']
                st.markdown('**' + escape(video['title']) + '**')
                published = 'Published ' + date.fromisoformat(video['published_at']).strftime('%d %b %Y') if video.get('published_at') else 'Publication date not supplied'
                st.caption(video['publisher'] + ' · ' + published + ' · Recorded film')
                st.caption(video['license'])
                watch_url = _safe_url(video['watch_url'])
                if video['embeddable_verified'] and watch_url:
                    st.video(watch_url, autoplay=False)
                st.caption('Playback may depend on YouTube settings. You can also open the film from the port’s website.')
                source_url = _safe_url(video['source_page'])
                if source_url:
                    st.link_button('Open official port film', source_url)
