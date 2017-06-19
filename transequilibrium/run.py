import configparser
import os
import sys

import tweepy

import azure
import lock
import pathutils
import twitter


def die(msg):
    '''
    Print the message and terminate.

    msg:
        The message to print.
    '''
    print(msg, file=sys.stderr)
    raise SystemExit(1)


class Runner:
    '''
    Run the application.
    '''

    def __init__(self, config_path):
        '''
        Initialize a `Runner` instance.

        config_path:
            The path to the configuration file containing the various keys,
            user name to target, etc.
        '''
        self._config_path = config_path
        self._config = configparser.ConfigParser()

        try:
            self._config.read(config_path)
        except configparser.MissingSectionHeaderError:
            die('The configuration file "{}" is not valid.'.format(self._config_path))

        self._my_user_name = self._get('app', 'my-user-name')
        self._target_user_name = self._get('app', 'target-user-name')

        self._dir = os.path.join(os.path.expanduser('~'),
                                 '.transequilibrium',
                                 '{}-{}'.format(self._my_user_name, self._target_user_name))
        pathutils.makedirs(self._dir)

        self._lock = None

    def __del__(self):
        if self._lock is not None:
            print('WARNING: The Runner was freed without calling the stop method.')

    def run(self):
        '''
        Start translating the tweets.
        '''
        def still_waiting_cb():
            print('Waiting for the lock (is another instance running?).')

        self._lock = lock.FileLock(os.path.join(self._dir, 'lock'),
                                   timeout=2 * 60,
                                   still_waiting_cb=still_waiting_cb)
        self._lock.acquire()

        auth = self._get_auth()

        translator = azure.Translator(self._get('translator-api', 'client-secret'))

        client = twitter.Client(
            translator,
            auth,
            self._my_user_name,
            self._target_user_name,
            self)
        client.process_tweets()

    def stop(self):
        if self._lock:
            self._lock.release()
            self._lock = None

    def _get_last_processed_file(self, mode):
        return open(os.path.join(self._dir, 'last-processed'), mode)

    def get_last_processed(self):
        '''
        Get the ID of the last processed tweet or, if no tweet was processed, the
        start value from the configuration file.

        Return value:
            A string identifying the last processed tweet.
        '''
        try:
            with self._get_last_processed_file('r') as last_processed:
                return last_processed.read().strip()
        except IOError:
            return self._get('app', 'start-since')

    def set_last_processed(self, tweet_id):
        '''
        Set the ID of the last processed tweet.

        tweet_id:
            The ID of the most recent tweet which was processed.
        '''
        with self._get_last_processed_file('w') as last_processed:
            last_processed.write(tweet_id)

    def save_last_processed_log(self, log_entry):
        '''
        Save log_entry in the log file.

        log_entry:
            A message to dump to the log file.
        '''
        with open(os.path.join(self._dir, 'log'), 'a') as log_file:
            log_file.write(log_entry)

        print(log_entry, end='')

    def _get_auth(self):
        '''
        Returns a `tweepy.OAuthHandler` to authenticate against Twitter for this
        instance's twitter account.

        Return value:
            A `tweepy.OAuthHandler` instance.
        '''
        auth = tweepy.OAuthHandler(
            self._get('twitter-api', 'consumer-key'),
            self._get('twitter-api', 'consumer-secret'))

        auth.set_access_token(
            self._get('twitter-api', 'access-token'),
            self._get('twitter-api', 'access-token-secret'))

        return auth

    def _get(self, section_name, option_name):
        '''
        Get the configuration key for `section_name` and `option_name` or terminate
        the program is the option is not set or is empty.

        section_name:
            The section where the option is.
        option_name:
            The name of the option to get.
        Return value:
            A string for the specified option.
        '''
        try:
            section = self._config[section_name]
        except KeyError:
            die('Section "{}" is missing from configuration file "{}".'.format(
                section_name,
                self._config_path,
                ))

        try:
            value = section[option_name]
        except KeyError:
            die('Option "{}" in section "{}" is missing from configuration file "{}".'.format(
                option_name,
                section_name,
                self._config_path,
                ))

        value = value.strip()

        if not value:
            die('Option "{}" in section "{}" in configuration file "{}" is empty.'.format(
                option_name,
                section_name,
                self._config_path,
                ))

        return value


def main():
    '''
    Start a `Runner` with the options specified on the command line.
    '''
    if len(sys.argv) != 2:
        die('{} CONFIG-FILE'.format(sys.argv[0]))

    runner = Runner(sys.argv[1])
    try:
        runner.run()
    finally:
        runner.stop()


if __name__ == '__main__':
    main()
