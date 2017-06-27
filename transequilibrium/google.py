import googleapiclient.discovery

import escaping


class Translator:
    '''
    Translate text between languages.
    '''

    def __init__(self, dev_key, model=None):
        '''
        Initializes a `Translator`.

        dev_key:
            A developer key for the translation API.
        model:
            The model to use. Either 'base' or 'nmt'.
        '''
        if model is None:
            model = 'nmt'
        assert model in ('base', 'nmt')
        self._model = model

        self._service = googleapiclient.discovery.build('translate', 'v2', developerKey=dev_key)

    def translate(self, from_lang, to_lang, text):
        '''
        Translate `text` from `from_lang` to `to_lang`.

        Return value:
            The translated text.
        '''
        # pylint: disable=no-member
        res = self._service.translations().list(
            q=[text],
            source=from_lang,
            target=to_lang,
            model=self._model,
            ).execute()
        return escaping.html_unescape(res['translations'][0]['translatedText'])


def main():
    import sys
    import equilibrium

    args = sys.argv[1:] + [None, None]
    model = args[0]
    text = args[1]

    equilibrium.debug_run(
        lambda key: Translator(key, model),
        '.google-translate.cfg',
        text)


if __name__ == "__main__":
    main()
