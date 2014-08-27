yageins
=======

Yet Another Github Event IRC Notification Service

About
=====

HTTP daemon listening for custom github notifications and submitting them to [II](http://tools.suckless.org/ii/)

It supports following events:

* push to branch
* create branch
* delete branch
* pull_request state change
* issue state change
* comment on issue or pull request

Usage
=====

python server.py --config=yageins.cfg


