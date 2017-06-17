import re

import tweepy


class Client:
    '''
    Twitter client which runs the application.
    '''

    def __init__(self, translator, auth, target_user_name, start_since):
        '''
        Initialize a `Client` instance.
        '''
        self._translator = translator
        self._api = tweepy.API(auth)
        self._target_user_name = target_user_name
        self._start_since = int(start_since)

    def process_tweets(self):
        '''
        Run the client on the new tweets available.
        '''
        for tweet in self._get_tweets(10):
            self._process_tweet(tweet)

    def _get_tweets(self, max_count):
        '''
        Get tweets for the user since the last tweet which was translated.

        max_count:
            The maximum number of tweets to get.
        Return value:
            A list of tweets sorted from the oldest to the newest.
        '''
        cursor = tweepy.Cursor(
            self._api.user_timeline,
            self._target_user_name,
            since_id=self._start_since)

        tweets = list(cursor.items())
        tweets.reverse()
        del tweets[max_count:]

        return tweets

    @staticmethod
    def _escape_tweet_text(text):
        text = re.sub('@([a-zA-Z0-9_]+)',
                      r'<transequilibrium:mention who="\1"></transequilibrium:mention>',
                      text)
        text = re.sub('#([a-zA-Z0-9_]+)',
                      r'<transequilibrium:hashtag tag="\1"></transequilibrium:hashtag>',
                      text)
        return text

    @staticmethod
    def _unescape_tweet_text(text):
        text = re.sub('<transequilibrium:mention who="([^"]+)"> *</transequilibrium:mention>',
                      r'@\1',
                      text)
        assert '<transequilibrium:mention>' not in text
        assert '</transequilibrium:mention>' not in text

        text = re.sub('<transequilibrium:hashtag tag="([^"]+)"> *</transequilibrium:hashtag>',
                      r'#\1',
                      text)
        assert '<transequilibrium:hashtag>' not in text
        assert '</transequilibrium:hashtag>' not in text

        return text

    def _process_tweet(self, tweet):
        '''
        Translate a tweet and post the translated one.

        tweet:
            The tweet to translate.
        '''
        res = self._translator.find_equilibrium('en', 'ja', self._escape_tweet_text(tweet.text))
        # FIXME: Post the translation and save the status somewhere.
        print(self._unescape_tweet_text(res.text))
