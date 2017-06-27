TransEquilibrium
================

[TransEquilibrium](https://github.com/barisione/transequilibrium/) is a Twitter bot which translates a user's tweets back and forth between English and Japanese until the translation is stable, that is translating the tweet further is not going to change it any more.

The idea comes from [TranslationParty](http://www.translationparty.com/), but is applied to Twitter.

[@reTrumplation](https://twitter.com/reTrumplation), translating Donald Trump's tweets, is the reason this bot was written.

**What's the point?**<br/>
There's no point.

**Why Japanese?**<br/>
I thought other languages, like Russian, could be more fun, but Japanese seems to be the worst translated language, which gives the funnier results.

**Who are you?**<br/>
[This is me](http://www.barisione.org/).

**What do you use to translate text?**<br/>
The Microsoft Azure Translator API which is behind Bing Translator.

**How do you translate the text?**<br />
TransEquilibrium can use Azure Translator or Google Translate (either using the “base” model or the neural network-based model called “nmt”).

1. Google with the “nmt” model produces the best sentences which actually have some kind of meaning.
2. Azure is the second best, but sentences not always have a meaning.
3. Google with the “base” model produces the worst quality sentences. Moreover, the sentences are often very long, so not suitable to tweeting.

**Something the bot said is offensive or inappropriate**<br />
Sorry. 😞<br />
Unfortunately this is unavoidable with a bot that works automatically.
