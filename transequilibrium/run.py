import configparser
import sys

import tweepy

import azure
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

    def run(self):
        '''
        Start translating the tweets.
        '''
        auth = self._get_auth()

        translator = azure.Translator(self._get('translator-api', 'client-secret'))

        client = twitter.Client(
            translator,
            auth,
            self._get('app', 'target-user-name'),
            self._get('app', 'start-since'))
        client.process_tweets()

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
    runner.run()


if __name__ == '__main__':
    main()
