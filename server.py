from flask import Flask, request
import sys
import json
import ConfigParser
from optparse import OptionParser
import os

# TODO : add exception handling when there are no branches_to_channels
# TODO : add global default channel for every unconfigured channel

app = Flask(__name__)

__report_indent = [0]

def debug(fn):
    def wrap(self, *params,**kwargs):
        call = wrap.callcount = wrap.callcount + 1

        indent = ' ' * __report_indent[0]
        fc = "%s(%s)" % (fn.__name__, ', '.join(
            [a.__repr__() for a in params] +
            ["%s = %s" % (a, repr(b)) for a,b in kwargs.items()]
        ))

        #debug = True
        if self.debug == 'True':
            print "%s%s called [#%s]" % (indent, fc, call)
            __report_indent[0] += 1
            ret = fn(self, *params,**kwargs)
            __report_indent[0] -= 1
            print "%s%s returned %s [#%s]" % (indent, fc, repr(ret), call)
            return ret
        else:
            ret = fn(self, *params,**kwargs)
            return ret
    wrap.callcount = 0
    return wrap


class Options:
    """
    @summary: Class responsible for handling options
    """
    def __init__(self, args):
        self.parser = OptionParser()
        self.args = args
        self.parser.add_option("--config",
                               dest="config",
                               default="yageins.cfg",
                               help="Path to yageins cofig file",
                               metavar="CONFIG")
        self.parser.add_option("--debug",
                               dest="debug",
                               default=False,
                               help="Enable debug True|False",
                               metavar="DEBUG")
        (self.options, self.args) = self.parser.parse_args()
        self.debug = self.options.debug

    def __repr__(self):
        return 'Options'

    @debug
    def get_options(self):
	    return self.options

class Config():
    def __init__(self, options):
        self.options = options
        self.debug = self.options.debug
        self.config = ConfigParser.RawConfigParser()
        self.config.read(self.options.config)

    @debug
    def get_config(self):
        return self.config


class IrcChannel:
    def __init__(self, channel_name, config, options):
        self.name = channel_name
        self.path = config.get(channel_name, 'path')
        self.debug = options.debug
        #echo %s | timeout -k 6 3 tee -a '%s' >/dev/null
        self.write_command = config.get('global', 'write_command')

    def __repr__(self):
        return 'IrcChannel'

    @debug
    def write_to_channel(self, message):
        command = self.write_command % (message, self.path)
        os.system(command)
        return True


class Yageins:
    def __init__(self, config, options):
        self.options = options
        self.config = config
        self.debug = self.options.debug
        self.host = self.config.get('global', 'host')
        self.port = self.config.getint('global', 'port')
        self.event_messages = {
                                "push" : "%s pushed to %s %s: %s",
                                "create" : "%s created branch %s %s",
                                "delete" : "%s deleted branch %s %s",
                                "pull_request" : "%s changed pull request state to '%s' for branch %s %s",
                                "issues" : "%s changed issue state for %s to %s %s",
                                "issue_comment" : "%s commented on issue '%s' %s",
                                "pull_request_review_comment" : "%s commented on '%s' %s"
                              }

    def __repr__(self):
        return 'Yageins'

    @debug
    def _write_to_channel(self, channel_name, message, message_type='push'):
        channel = IrcChannel(channel_name, config, self.options)
        return channel.write_to_channel(message)

    @debug
    def _get_event_message(self, event_name):
        pass

    @debug
    def _parse_channels(self, repo_name):
        """ Should return dictionary of repo_branch : channel_name """
        channels = {}
        try:
            channels_map = self.config.get(repo_name, 'branches_to_channels').split(',')
            for channel_pair in channels_map:
                branch_name, channel_name = channel_pair.split(':')
                channels[branch_name] = channel_name
        except Exception, e:
            print 'No channel configured for %s' % repo_name
            channels[repo_name] = self.config.get('global', 'default_channel')
        return channels

    @debug
    def _channel_for(self, repo_name, branch_name):
        channels = self._parse_channels(repo_name)
        try:
            channel_name = channels[branch_name]
        except Exception, e:
            try:
                channel_name = self.config.get(repo_name, 'default_channel')
            except Exception, e:
                channel_name = self.config.get('global', 'default_channel')
        return channel_name

    @debug
    def _handle_push(self, req_data, action):
        repo_name = req_data['repository']['full_name']
        pusher = req_data['pusher']['name']
        deleted = req_data['deleted']
        if deleted == True:
            deleted_message = 'and deleted it'
        else:
            deleted_message = ''
        compare_url = req_data['compare']
        branch_name = req_data['ref'].replace('refs/heads/','')
        message = self.event_messages[action] % (pusher, branch_name, deleted_message, compare_url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_pull_request(self, req_data, action):
        repo_name = req_data['pull_request']['base']['repo']['full_name']
        pull_request_action = req_data['action']
        compare_url = req_data['pull_request']['_links']['html']['href']
        pusher = req_data['sender']['login']
        branch_name = req_data['pull_request']['base']['ref']
        message = self.event_messages[action] % (pusher, pull_request_action, branch_name, compare_url)
        print message
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_delete_branch(self, req_data, action):
        pusher = req_data['sender']['login']
        branch_name = req_data['ref']
        repo_name = req_data['repository']['full_name']
        url = req_data['repository']['clone_url']
        message = self.event_messages[action] % (pusher, branch_name, url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_create_branch(self, req_data, action):
        pusher = req_data['sender']['login']
        branch_name = req_data['ref']
        repo_name = req_data['repository']['full_name']
        url = req_data['repository']['clone_url']
        message = self.event_messages[action] % (pusher, branch_name, url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_issues(self, req_data, action):
        issue_action = req_data['action']
        repo_name = req_data['repository']['full_name']
        issue_name = "'" + req_data['issue']['title'] + "'"
        who = req_data['sender']['login']
        url = req_data['issue']['html_url']
        branch_name = 'master'
        message = self.event_messages[action] % (who, issue_name, issue_action, url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_issue_comment(self, req_data, action):
        who = req_data['comment']['user']['login']
        url = req_data['comment']['html_url']
        issue_title = req_data['issue']['title']
        repo_name = req_data['repository']['full_name']
        branch_name = None
        message = self.event_messages[action] % (who, issue_title, url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_pull_request_review_comment(self, req_data, action):
        who = req_data['comment']['user']['login']
        url = req_data['comment']['html_url']
        issue_title = req_data['issue']['title']
        repo_name = req_data['repository']['full_name']
        branch_name = None
        message = self.event_messages[action] % (who, issue_title, url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_ping(self):
        return True
        
    @debug
    def _handle_commit(self, req_data):
        pass

    @debug
    def _route_request(self, request):
        data = json.loads(request.data)
        action = request.headers.get('X-GitHub-Event')
        if action == 'create':
            self._handle_create_branch(data, action)
        elif action == 'delete':
            self._handle_delete_branch(data, action)
        elif action == 'pull_request':
            self._handle_pull_request(data, action)
        elif action == 'push':
            self._handle_push(data, action)
        elif action == 'issues':
            self._handle_issues(data, action)
        elif action == 'issue_comment':
            self._handle_issue_comment(data, action)
        elif action == 'pull_request_review_comment':
            self._handle_pull_request_review_comment(data, action)
        elif action == 'ping':
            self._handle_ping()
        else:
            print "Unknown action %s " % action
        pass

    @debug
    def parse(self, request):
        self._route_request(request)
        return True


@debug
@app.route('/')
def slash():
    return 'Hi it\'s Yageins here - for submitting payload got to /payload'

@debug
@app.route('/payload', methods=['POST'])
def payload():
    if yageins.parse(request):
        return 'OK'
    else:
        return 'error'

if __name__ == '__main__':
    options = Options(sys.argv).get_options()
    config = Config(options).get_config()
    yageins = Yageins(config, options)
    app.debug = options.debug
    app.run(
            host=yageins.host,
            port=yageins.port
    )
