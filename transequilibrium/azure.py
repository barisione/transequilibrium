import collections
import datetime
import textwrap
import time
import urllib.parse
import xml.etree.ElementTree

import requests

import escaping


Result = collections.namedtuple('Result', ['equilibrium', 'text'])


class TranslationFailure(Exception):
    pass


class AuthTokenClient:
    '''
    Get a token from the Microsoft API and renews it when needed.
    '''

    def __init__(self, client_secret):
        '''
        Initialize a `AuthTokenClient`.

        client_secret:
            A client secret for the translation API.
        '''
        self._client_secret = client_secret

        self._token = None
        self._token_valid_until = datetime.datetime(1970, 1, 1)

    @staticmethod
    def _now():
        return datetime.datetime.now()

    def _fetch_token(self):
        url = 'https://api.cognitive.microsoft.com/sts/v1.0/issueToken'
        headers = {
            'Ocp-Apim-Subscription-Key': self._client_secret
            }

        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.content.decode('utf-8')

    def get_token(self):
        '''
        Get an authorization token.

        The token is internally cached and fetched again only when it expires.

        Return value:
            A token string which can be used for the translation API.
        '''
        now = self._now()
        if now > self._token_valid_until:
            self._token = self._fetch_token()
            self._token_valid_until = now + datetime.timedelta(minutes=5)

        return self._token


class Translator:
    '''
    Translate text between languages.
    '''

    def __init__(self, client_secret):
        '''
        Initializes a `Translator`.

        client_secret:
            A client secret for the translation API.
        '''
        self._auth = AuthTokenClient(client_secret)

    def translate(self, from_lang, to_lang, text):
        '''
        Translate `text` from `from_lang` to `to_lang`.

        Return value:
            The translated text.
        '''
        bearer_token = 'Bearer ' + self._auth.get_token()
        headers = {
            'Authorization': bearer_token,
            }

        def quote(string):
            return urllib.parse.quote(string, safe='')

        url = 'http://api.microsofttranslator.com/v2/Http.svc/Translate?' \
              'text={text}&from={from_lang}&to={to_lang}'.format(
                  text=quote(text),
                  from_lang=quote(from_lang),
                  to_lang=quote(to_lang))

        last_connection_error = None

        for retry in range(4):
            try:
                response = requests.get(url, headers=headers)
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as exc:
                # Sometimes there seems to be some transient flakiness, so we retry.
                last_connection_error = exc
                time.sleep(retry)
                continue

            translation_element = xml.etree.ElementTree.fromstring(response.text.encode('utf-8'))
            if translation_element.text is None:
                raise TranslationFailure(
                    'Failed to translate the text. Got:\n{}.'.format(
                        textwrap.indent(response.text, ' ' * 4)))

            return escaping.html_unescape(translation_element.text)

        assert last_connection_error is not None
        # pylint: disable=raising-bad-type
        raise last_connection_error


def main():
    import sys
    import equilibrium

    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    else:
        text = None

    equilibrium.debug_run(Translator, '.bing-translator.cfg', text)


if __name__ == "__main__":
    main()
