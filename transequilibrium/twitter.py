import collections
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
        self._target_user_name = target_user_name
        self._last_processed = last_processed

        self._api = tweepy.API(auth,
                               wait_on_rate_limit=True,
                               wait_on_rate_limit_notify=True,
                               retry_count=5)
        self._my_user = self._api.me()
        self._following = set()

    def process_tweets(self):
        '''
        Run the client on the new tweets available.
        '''
        for following in tweepy.Cursor(self._api.friends_ids, user_id=self._my_user.id_str).items():
            self._following.add(following)

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

    def _log(self, json_log_entry):
        log_entry = json.dumps(json_log_entry,
                               indent=4,
                               separators=(',', ': '))
        # The save function doesn't really use JSON (and I don't want it to do it either),
        # but we are using JSON just because it's a convenient way to dump down some text.
        self._last_processed.save_last_processed_log(log_entry + '\n')

    def _follow_mentions(self, tweet):
        for user_dict in tweet.entities['user_mentions']:
            user_id = user_dict['id']
            if user_id not in self._following:
                self._api.create_friendship(user_id=user_id)
                self._log({'following': user_id})
                self._following.add(user_id)

    def _post_tweet(self, text):
        # It would be nice to post this as a reply to the original tweet.
        # Unfortunately, using a mention at the beginning and in_reply_to_status_id still
        # seems to be affected by the 140 characters limit.
        # Moreover, I'm not sure spamming with replies would always be a good idea.

        # The length seems to be now in characters, not bytes, so this will work fine.
        text = text[:140]
        return self._api.update_status(text)

    @staticmethod
    def _get_tweet_url(user_name, tweet_id):
        # Usually the original URL is in tweet.entities['urls'][0]['expanded_url'], but not
        # for retweets, so we just build the URL here. If you follow the link and it's a
        # retweet, then Twitter redirects you to the original one.
        return 'https://twitter.com/{}/status/{}'.format(user_name, tweet_id)

    def _process_tweet(self, tweet):
        '''
        Translate a tweet and post the translated one.

        tweet:
            The tweet to translate.
        '''
        log_details = [
            ('original-id', tweet.id),
            ('original-url', self._get_tweet_url(self._target_user_name, tweet.id)),
            ('original-time', tweet.created_at.isoformat()),
            ('original-text', tweet.text),
            ]

        if hasattr(tweet, 'retweeted_status'):
            # Note that retweets with an extra comment don't have retweeted_status, but
            # they have quoted_status, so we don't skip them.
            log_details += [
                ('skipped-because-retweet', True),
                ]
        else:
            self._follow_mentions(tweet)

            res = self._translator.find_equilibrium('en', 'ja',
                                                    self._escape_tweet_text(tweet.text))
            translated_text = self._unescape_tweet_text(res.text)
            new_tweet = self._post_tweet(translated_text)

            log_details += [
                ('translated-id', new_tweet.id),
                ('translated-url', self._get_tweet_url(self._my_user.id, new_tweet.id)),
                ('translated-time', new_tweet.created_at.isoformat()),
                ('translated-text', new_tweet.text),
                ('equilibrium-reached', res.equilibrium),
                ]

        self._last_processed.set_last_processed(tweet.id_str)
        # We save logs after the ID, so there's a chance we actually fail to save logs for
        # this tweet. This is better than retweeting the same thing twice.
        self._log(collections.OrderedDict(log_details))
