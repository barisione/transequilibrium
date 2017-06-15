import collections
import datetime
import textwrap
import time
import urllib.parse
import xml.etree.ElementTree

import requests


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
            except requests.exceptions.ConnectionError as exc:
                # Sometimes there seems to be some transient flakiness, so we retry.
                last_connection_error = exc
                time.sleep(retry)
                continue

            translation_element = xml.etree.ElementTree.fromstring(response.text.encode('utf-8'))
            if translation_element.text is None:
                raise TranslationFailure(
                    'Failed to translate the text. Got:\n{}.'.format(
                        textwrap.indent(response.text, ' ' * 4)))

            return translation_element.text

        assert last_connection_error is not None
        # pylint: disable=raising-bad-type
        raise last_connection_error

    def find_equilibrium(self, main_lang, intermediate_lang, initial_text, translation_cb=None):
        '''
        Translated `initial_text` between `main_lang` and `intermediate_lang` until
        equilibrium is found, i.e. retranslating the text again doesn't change the
        translation.

        main_lang:
            The language for `initial_text`.
        intermediate_lang:
            The intermediate language for the translation.
        initial_text:
            The text to translate.
        translation_cb:
            An optional function to call when a translation is made (for debugging
            purposes).
            The function's gets as parameters the retry count, the language for the
            translated text (i.e. alternatively `intermediate_lang` and `main_lang`),
            ane the translated text.
        '''
        last_text = initial_text

        for retry_count in range(15):
            intermediate_text = self.translate(main_lang, intermediate_lang, last_text)
            if translation_cb:
                translation_cb(retry_count, intermediate_lang, intermediate_text)

            retranslated_text = self.translate(intermediate_lang, main_lang, intermediate_text)
            if translation_cb:
                translation_cb(retry_count, main_lang, retranslated_text)

            if last_text == retranslated_text:
                # Equilibrium!
                return Result(True, last_text)

            # No equilibrium (yet?).
            last_text = retranslated_text

        # We gave up as it doesn't look like we are going to reach an equilibrium.
        return Result(False, last_text)


def main():
    import os
    import sys

    try:
        client_secret_path = '~/.bing-translator.cfg'
        with open(os.path.expanduser(client_secret_path)) as client_secret_file:
            client_secret = client_secret_file.read().strip()
    except IOError:
        print('Specify a secret for the Bing Translator API in "{}".'.format(client_secret_path),
              file=sys.stderr)
        raise SystemExit(1)

    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    else:
        text = input('Text: ')

    def translator_cb(counter, lang, translated_text):
        print('[{counter}] {lang}: {translated_text}'.format(
            counter=counter,
            lang=lang,
            translated_text=translated_text,
            ))

    translator = Translator(client_secret)
    res = translator.find_equilibrium('en', 'ja', text, translator_cb)
    equilibrium_text = '' if res.equilibrium else ' (equilibrium not found)'
    print('RESULT{}: {}'.format(equilibrium_text, res.text))


if __name__ == "__main__":
    main()
