try:
    import html
    #pylint: disable=invalid-name
    html_unescape = html.unescape
except (ImportError, NameError):
    import HTMLParser
    #pylint: disable=invalid-name
    html_unescape = HTMLParser.HTMLParser().unescape
