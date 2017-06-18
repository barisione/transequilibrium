import collections
import datetime
import json
import re

import tweepy


class Client:
    '''
    Twitter client which runs the application.
    '''

    def __init__(self, translator, auth, target_user_name, last_processed):
        '''
        Initialize a `Client` instance.
        '''
        self._translator = translator
        self._api = tweepy.API(auth)
        self._target_user_name = target_user_name
        self._last_processed = last_processed

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
            since_id=self._last_processed.get_last_processed())

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
        translated_text = self._unescape_tweet_text(res.text)
        # FIXME: Post the translation.
        print(translated_text)

        self._last_processed.set_last_processed(tweet.id_str)

        # We save logs after the ID, so there's a chance we actually fail to save logs for
        # this tweet. This is better than retweeting the same thing twice.

        # Usually the original URL is in tweet.entities['urls'][0]['expanded_url'], but not
        # for retweets, so we just build the URL here. If you follow the link and it's a
        # retweet, then Twitter redirects you to the original one.
        original_url = 'https://twitter.com/{}/status/{}'.format(self._target_user_name, tweet.id)
        log_entry_dict = collections.OrderedDict([
            ('original-id', tweet.id),
            ('original-url', original_url),
            ('original-time', tweet.created_at.isoformat()),
            ('original-text', tweet.text),
            ('translated-id', None),
            ('translated-time', datetime.datetime.now().isoformat()),
            ('translated-text', translated_text),
            ('equilibrium-reached', res.equilibrium),
            ])
        log_entry = json.dumps(log_entry_dict,
                               indent=4,
                               separators=(',', ': '))
        # The save function doesn't really use JSON (and I don't want it to do it either),
        # but we are using JSON just because it's a convenient way to dump down some text.
        self._last_processed.save_last_processed_log(log_entry + '\n')
