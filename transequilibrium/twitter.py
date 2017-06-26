import collections
import json
import re
import time

import tweepy

import escaping
import equilibrium
import offensive


class Client:
    '''
    Twitter client which runs the application.
    '''

    #pylint: disable=too-many-arguments
    def __init__(self, translator, auth, my_user_name, target_user_name, last_processed):
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
        # We need the screen name before creating the API object, so here we check
        # everything is correct.
        # Ideally this should be reorganised to avoid this problem but I'm not sure
        # how to layer this properly.
        assert self._my_user.screen_name == my_user_name

        self._following = set()

    def process_tweets(self):
        '''
        Run the client on the new tweets available.
        '''
        for following in tweepy.Cursor(self._api.friends_ids, user_id=self._my_user.id_str).items():
            self._following.add(following)

        for i, tweet in enumerate(self._get_tweets(10)):
            # Try to space tweets a bit to avoid being suspended.
            sleep_multiplier = min(i, 5)
            time.sleep(sleep_multiplier * 15)

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
            since_id=self._last_processed.get_last_processed(),
            tweet_mode='extended')

        tweets = list(cursor.items())
        tweets.reverse()
        del tweets[max_count:]

        return tweets

    @staticmethod
    def _sanitize_tweet(tweet):
        # This is inspired by https://github.com/wjt/fewerror/ by Will Thompson.
        text = tweet.full_text
        entities = tweet.entities

        # First get all the entities (with information on what is inside).
        flat_entities = []
        for entity_type, entity_key, value_key in (('media', 'media', 'media_url'),
                                                   ('url', 'urls', 'url'),
                                                   ('mention', 'user_mentions', 'screen_name'),
                                                   ('hashtag', 'hashtags', 'text')):
            for entity in entities.get(entity_key, []):
                flat_entities.append({
                    'type': entity_type,
                    'key': entity_key,
                    'entity': entity,
                    'value': entity[value_key],
                    })

        # Sort them so we start from the end (as we are replacing text at a fixed
        # position.
        flat_entities.sort(key=lambda item: item['entity']['indices'],
                           reverse=True)

        # And finally replace the entity with a tag which the translator should
        # ignore.
        for info in flat_entities:
            i, j = info['entity']['indices']
            assert '"' not in info['value']
            tag = '<transequilibrium:escaped ' + \
                  'type="{type}" value="{value}"></escaped>'.format(**info)
            text = text[:i] + tag + text[j:]

        # Twitter returns HTML-escaped strings, but expects unescaped strings.
        # Probably this was done to avoid HTML injection.
        text = escaping.html_unescape(text)

        return text.strip()

    @staticmethod
    def _unsanitize_tweet_text(text):
        replacements = {
            'media': '{}',
            'url': '{}',
            'mention': '@{}',
            'hashtag': '#{}',
            }

        def re_cb(match):
            entity_type = match.group(1)
            entity_value = match.group(2)
            unsanitized_entity = replacements[entity_type].format(entity_value)
            # The translator tends to eat spaces next to URLs, so we make sure there's
            # spaces (and the regex eats all nearby spaces anyway).
            return ' {} '.format(unsanitized_entity)

        # Everybody know that the best way to parse XML/HTML is regexes.
        text = re.sub(' *<transequilibrium:escaped type="([^"]+)" value="([^"]+)"> *',
                      re_cb,
                      text)
        text = re.sub(' *</transequilibrium:escaped> *',
                      ' ',
                      text)
        text = re.sub(' +', ' ', text)
        assert '<transequilibrium:escaped' not in text
        assert '</transequilibrium:escaped' not in text
        return text

    @staticmethod
    def _serialize_json(json_object):
        serialized = json.dumps(json_object,
                                indent=4,
                                separators=(',', ': '))
        if not serialized.endswith('\n'):
            serialized += '\n'
        return serialized

    @staticmethod
    def _serialize_list_to_ordered_dict(json_list):
        return Client._serialize_json(collections.OrderedDict(json_list))

    def _log(self, log_entry, extra_name=None):
        self._last_processed.save_last_processed_log(log_entry, extra_name)

    def _log_tweet_json(self, tweet):
        if tweet is None:
            return

        #unformatted_json_text = tweet._json
        #parsed_json = json.loads(unformatted_json_text)
        #pylint: disable=protected-access
        serialized_json = self._serialize_json(tweet._json)

        extra_name = '{}-{}.json'.format(tweet.user.screen_name, tweet.id)

        self._log(serialized_json, extra_name)

    def _follow_mentions(self, tweet):
        for user_dict in tweet.entities['user_mentions']:
            user_id = user_dict['id']
            if user_id not in self._following:
                screen_name = self._api.get_user(user_id).screen_name
                url = 'https://twitter.com/{}'.format(screen_name)
                self._api.create_friendship(user_id=user_id)
                self._following.add(user_id)
                self._log(
                    self._serialize_list_to_ordered_dict([
                        ('following-id', user_id),
                        ('following-screen-name', screen_name),
                        ('following-url', url),
                        ]))

    @staticmethod
    def _limit_text_length(text):
        text = text.strip()

        # Note that, nowadays, the length is in characters, not bytes.
        limit = 140
        if len(text) <= limit:
            return text

        last_space = text.rfind(' ', 0, limit + 1)
        # Let's assume the translator doesn't give us a 140+ character long word (as the
        # original tweet cannot be like this either).
        # Dealing with this would be trivial, but I'd rather know what is going on.
        assert last_space > 0

        return text[:last_space].rstrip()

    def _post_tweet(self, text, original_tweet_id):
        # It would be nice to post this as a reply to the original tweet.
        # Unfortunately, using a mention at the beginning and in_reply_to_status_id still
        # seems to be affected by the 140 characters limit.
        # Moreover, I'm not sure spamming with replies would always be a good idea.
        return self._api.update_status(
            self._limit_text_length(text),
            tweet_mode='extended',
            attachment_url=self._get_tweet_url(self._target_user_name, original_tweet_id))

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
            ('original-text', tweet.full_text),
            ]

        if hasattr(tweet, 'retweeted_status'):
            # Note that retweets with an extra comment don't have retweeted_status, but
            # they have quoted_status, so we don't skip them.
            log_details += [
                ('skipped-because-retweet', True),
                ]
            intermediate_translations = None
            new_tweet = None
        else:
            self._follow_mentions(tweet)

            intermediate_translations = []
            def translation_cb(counter, language, intermediate_text):
                intermediate_translations.append(collections.OrderedDict([
                    ('counter', counter),
                    ('language', language),
                    ('text', intermediate_text),
                    ]))

            sanitized_text = self._sanitize_tweet(tweet)
            equilibrium_reached, sanitized_translated_text = equilibrium.find_equilibrium(
                self._translator,
                'en', 'ja', sanitized_text,
                translation_cb)
            translated_text = self._unsanitize_tweet_text(sanitized_translated_text)
            new_tweet = self._post_tweet(translated_text, tweet.id)

            if tweet.full_text != sanitized_text:
                log_details += [
                    ('original-sanitized-text', sanitized_text),
                    ]

            log_details += [
                ('translated-id', new_tweet.id),
                ('translated-url', self._get_tweet_url(self._my_user.id, new_tweet.id)),
                ('translated-time', new_tweet.created_at.isoformat()),
                ]

            # Maybe the tweet was shortened or mangled in some other way by Twitter.
            if translated_text != new_tweet.full_text:
                log_details += [
                    ('translated-initial-text', translated_text),
                    ]

            log_details += [
                ('translated-text', new_tweet.full_text),
                ('equilibrium-reached', equilibrium_reached),
                ]

            # For now we just log about offensiveness.
            # Later I can verify how useful this check is and, if needed, not post the
            # tweets.
            original_offensive = not offensive.tact(tweet.full_text)
            new_offensive = not offensive.tact(translated_text)
            if original_offensive and new_offensive:
                offensiveness = 'both'
            elif original_offensive:
                offensiveness = 'original'
            elif new_offensive:
                offensiveness = 'retranslated'
            else:
                offensiveness = 'none'

            log_details += [
                ('offensiveness', offensiveness),
                ]

        self._last_processed.set_last_processed(tweet.id_str)
        # We save logs after the ID, so there's a chance we actually fail to save logs for
        # this tweet. This is better than retweeting the same thing twice.
        self._log(self._serialize_list_to_ordered_dict(log_details))

        self._log_tweet_json(tweet)
        self._log_tweet_json(new_tweet)

        if intermediate_translations:
            json_text = self._serialize_json(intermediate_translations)
            extra_name = '{}-{}-translations.json'.format(tweet.user.screen_name, tweet.id)
            self._log(json_text, extra_name)
