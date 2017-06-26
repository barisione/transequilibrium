import collections


Result = collections.namedtuple('Result', ['equilibrium', 'text'])


def find_equilibrium(translator, main_lang, intermediate_lang, initial_text, translation_cb=None):
    '''
    Translate `initial_text` between `main_lang` and `intermediate_lang` until
    equilibrium is found, i.e. retranslating the text again doesn't change the
    translation.

    translator:
        A translator instance.
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
        intermediate_text = translator.translate(main_lang, intermediate_lang, last_text)
        if translation_cb:
            translation_cb(retry_count, intermediate_lang, intermediate_text)

        retranslated_text = translator.translate(intermediate_lang, main_lang, intermediate_text)
        if translation_cb:
            translation_cb(retry_count, main_lang, retranslated_text)

        if last_text == retranslated_text:
            # Equilibrium!
            return Result(True, last_text)

        # No equilibrium (yet?).
        last_text = retranslated_text

    # We gave up as it doesn't look like we are going to reach an equilibrium.
    return Result(False, last_text)


def debug_run(translator_new, config_basename, text=None):
    import os
    import sys

    try:
        config_path = os.path.join('~', config_basename)
        with open(os.path.expanduser(config_path)) as config_file:
            key = config_file.read().strip()
    except IOError:
        print('Specify a secret for the translator API in "{}".'.format(config_path),
              file=sys.stderr)
        raise SystemExit(1)

    translator = translator_new(key)

    if text is None:
        text = input('Text: ')

    def translator_cb(counter, lang, translated_text):
        print('[{counter}] {lang}: {translated_text}'.format(
            counter=counter,
            lang=lang,
            translated_text=translated_text,
            ))

    res = find_equilibrium(translator, 'en', 'ja', text, translator_cb)
    equilibrium_text = '' if res.equilibrium else ' (equilibrium not found)'
    print('RESULT{}: {}'.format(equilibrium_text, res.text))
