from flask import Flask, request
import sys
import json
import ConfigParser
from optparse import OptionParser
import os

app = Flask(__name__)

__report_indent = [0]

def debug(fn):
    def wrap(*params,**kwargs):
        call = wrap.callcount = wrap.callcount + 1

        indent = ' ' * __report_indent[0]
        fc = "%s(%s)" % (fn.__name__, ', '.join(
            [a.__repr__() for a in params] +
            ["%s = %s" % (a, repr(b)) for a,b in kwargs.items()]
        ))

        debug = True
        if debug == True:
            print "%s%s called [#%s]" % (indent, fc, call)
            __report_indent[0] += 1
            ret = fn(*params,**kwargs)
            __report_indent[0] -= 1
            print "%s%s returned %s [#%s]" % (indent, fc, repr(ret), call)
            return ret
        else:
            ret = fn(*params,**kwargs)
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

    def get_options(self):
	return self.options

class Config():
    def __init__(self, options):
        self.options = options
        self.config = ConfigParser.RawConfigParser()
        self.config.read(self.options.config)

    def get_config(self):
        return self.config


class IrcChannel:
    def __init__(self, channel_name, config):
        self.name = channel_name
        self.path = config.get(channel_name, 'path')
        #echo %s | timeout -k 6 3 tee -a '%s' >/dev/null
        self.write_command = config.get('global', write_command)

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
        self.secret_token = self.config.get('global', 'secret_token')
        self.event_messages = {
                                "push" : "%s pushed to %s: %s",
                                "create" : "%s created branch %s",
                                "delete" : "%s deleted branch %s",
                                "pull_request" : "pull request (%s) state changed (%s)"
                              }

    def __repr__(self):
        return 'Yageins'

    @debug
    def _write_to_channel(self, channel_name, message, message_type='push'):
        channel = IrcChannel(channel_name, config)
        return channel.write(message)

    @debug
    def _get_event_message(self, event_name):
        pass

    @debug
    def _parse_channels(self, repo_name):
        """ Should return dictionary of repo_branch : channel_name """
        channels = {}
        channels_map = self.config.get(repo_name, 'branches_to_channel').split(',')
        for channel_pair in channels_map:
            branch_name, channel_name = channel_pair.split(':')
            channels[repo_branch] = channel_name
        return channels

    @debug
    def _channel_for(self, repo_name, branch_name):
        channels = self._parse_channels(repo_name)
        channel_name = channels[branch_name]
        return channel_name

    @debug
    def _handle_push(self, req_data):
        repo_name = req_data['repository']['full_name']
        pusher = req_data['pusher']['name']
        message = req_data['head_commit']['message'].split('\n')[0]
        compare_url = req_data['compare']
        branch_name = req_data['ref'].replace('refs/heads/','')
        message = self.event_messages['push'] % (pusher, branch_name, compare_url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_merge_pull_request(self, req_data):
        repo_name = req_data['repository']['full_name']
        pusher = req_data['pusher']['name']
        message = req_data['head_commit']['message'].split('\n')[0]
        compare_url = req_data['compare']
        branch_name = req_data['ref'].replace('refs/heads/','')
        message = self.event_messages['push'] % (pusher, branch_name, compare_url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_delete_branch(self, req_data):
        repo_name = req_data['repository']['full_name']
        pusher = req_data['pusher']['name']
        message = req_data['head_commit']['message'].split('\n')[0]
        compare_url = req_data['compare']
        branch_name = req_data['ref'].replace('refs/heads/','')
        message = self.event_messages['push'] % (pusher, branch_name, compare_url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_create_branch(self, req_data):
        repo_name = req_data['repository']['full_name']
        pusher = req_data['pusher']['name']
        message = req_data['head_commit']['message'].split('\n')[0]
        compare_url = req_data['compare']
        branch_name = req_data['ref'].replace('refs/heads/','')
        message = self.event_messages['push'] % (pusher, branch_name, compare_url)
        self._write_to_channel(self._channel_for(repo_name, branch_name), message)

    @debug
    def _handle_commit(self, req_data):
        pass

    @debug
    def _route_request(self, req_data):
        if req_data['created'] == True:
            self._handle_create_branch(req_data)
        elif req_data['deleted'] == True:
            self._handle_delete_branch(req_data)
        elif 'Merge pull request' in req_data['head_commit']['message'].split('\n')[0]:
            self._handle_merge_pull_request(req_data)
        else:
            self._handle_push(req_data)
        pass

    @debug
    def parse(self, request):
        req = json.loads(str(request.data))
        self._route_request(req)
        print request.data
        return True


@app.route('/')
def slash():
    return 'Hi it\'s Yageins here - for submitting payload got to /payload'

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
