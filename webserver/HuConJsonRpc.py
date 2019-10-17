#!/usr/bin/python
""" 2018-12-11

The JSON RPC class to handle all incoming requests and return a well formed response.

Author: Sascha.MuellerzumHagen@baslerweb.com
"""

import os
from os.path import expanduser
import json
import subprocess
import time
import tempfile
import signal

from HuConLogMessage import HuConLogMessage


class HuConJsonRpc():
    """ This class implements the functionality of the which will the server provide.
    """

    # Name for the server to identification
    _SERVER_NAME = 'HuConRobot'

    # Folder where all custom code files are stored.
    _CODE_ROOT = os.path.join(expanduser("~"), 'hucon', 'code')

    # Folder where all custom code files are stored.
    _EXAMPLE_ROOT = os.path.join(os.path.abspath(os.path.join(os.getcwd(), os.pardir)), 'code')

    # Path to the version file.
    _VERSION_FILE = os.path.join(os.path.abspath(os.path.join(os.getcwd(), os.pardir)), '__version__')

    # Path to the password file.
    _PASSWORD_FILE = os.path.join(os.path.abspath(os.path.join(os.getcwd(), os.pardir)), 'password')

    # Path to the update file.
    _UPDATE_FILE = os.path.join(os.path.abspath(os.path.join(os.getcwd(), os.pardir)), 'update.sh')

    # Define the port on which the server should listening on.
    _LISTENING_PORT = 8080

    # Private key for the authorization to the key.
    _authorization_key = ''

    # Current version of the server.
    _version = 'beta'

    # Store the current running state
    _is_running = False

    # Store the current process to communicate with a running process
    _current_proc = None

    # Possible post data events stored as json format
    _possible_post_data = None

    # Queue for all log messages
    _log = HuConLogMessage()

    def __init__(self):
        """ Initialize the RPC server.
        """
        if os.path.exists(self._VERSION_FILE):
            with open(self._VERSION_FILE, 'r') as file:
                self._version = file.readline()

        if not os.path.exists(self._CODE_ROOT):
            os.makedirs(self._CODE_ROOT)

        print('%s v. %s' % (self._SERVER_NAME, self._version))
        print('Custom code path: \'%s\'' % self._CODE_ROOT)
        print('Example code path: \'%s\'' % self._EXAMPLE_ROOT)

    def handle_control(self, rpc_request):
        """ Handle the JSON RPC request.
        """
        if rpc_request['method'] == 'get_version':
            return self._get_version(rpc_request)
        elif rpc_request['method'] == 'poll':
            return self._poll(rpc_request)
        elif rpc_request['method'] == 'get_file_list':
            return self._get_file_list(rpc_request)
        elif rpc_request['method'] == 'create_folder':
            return self._create_folder(rpc_request)
        elif rpc_request['method'] == 'load_file':
            return self._load_file(rpc_request)
        elif rpc_request['method'] == 'save_file':
            return self._save_file(rpc_request)
        elif rpc_request['method'] == 'is_running':
            return self._get_is_running(rpc_request)
        elif rpc_request['method'] == 'execute':
            return self._execute(rpc_request)
        elif rpc_request['method'] == 'run':
            return self._run(rpc_request)
        elif rpc_request['method'] == 'kill':
            return self._kill(rpc_request)
        elif rpc_request['method'] == 'get_possible_post_data':
            return self._get_possible_post_data(rpc_request)
        elif rpc_request['method'] == 'event':
            return self._event(rpc_request)
        elif rpc_request['method'] == 'check_update':
            return self._check_update(rpc_request)
        elif rpc_request['method'] == 'update':
            return self._update(rpc_request)
        elif rpc_request['method'] == 'shutdown':
            return self._shutdown(rpc_request)
        else:
            return self._return_error(rpc_request['id'], 'Command not known.')

    def _get_rpc_response(self, rpc_id):
        """ Return a json rpc response message.
        """
        rpc_response = {}
        rpc_response['jsonrpc'] = '2.0'
        rpc_response['result'] = ''
        rpc_response['id'] = rpc_id

        return rpc_response

    def _return_error(self, rpc_id, error, status_code=400):
        """ Return an well formed error.
        """
        rpc_response = {}
        rpc_response['jsonrpc'] = '2.0'
        rpc_response['error'] = error
        rpc_response['id'] = rpc_id

        return (json.dumps(rpc_response), status_code)

    def _replace_hucon_requests(self, message):
        """ Print an answer from HuCon whenever the the message 'Hello HuCon!' is found.
        """
        search_string = 'print(\'Hello HuCon!\')'
        replace_string = 'print(\'Hello HuCon!\\n\\nHello human!\\nI am a Hu[man] Con[trolled] robot.\\n\')'
        if search_string in message:
            message = message.replace(search_string, replace_string)
        return message

    def _run_file(self, filename):
        """ Run the file and catch all output of it.
        """
        error_detected = False
        self._current_proc = subprocess.Popen(['python3', '-u', filename],
                                              bufsize=1,
                                              stdin=subprocess.PIPE,
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.STDOUT)

        while True:
            output = self._current_proc.stdout.readline().decode("utf-8")
            if output == '' and self._current_proc.poll() is not None:
                break
            if output:
                file_error_string = 'File "' + filename + '", l'
                if output.find(file_error_string) != -1:
                    error_detected = True
                # Replace the file error like 'File "/tmp/execute.py", line x, in'
                line = output.replace(file_error_string, '[red]Error: L')
                self._log.put(line)

        if not error_detected:
            self._log.put('')
            self._log.put('[green]Done ...')

        self._current_proc.poll()

        # Wait until the queue is empty or the timout occured
        timeout = 0
        while (self._log.empty() is False) and (timeout < 30):
            time.sleep(0.1)
            timeout = timeout + 1

    # ----------------------------------------------------------------------------------------------------------------------
    # JSON RPC API Methods
    # ----------------------------------------------------------------------------------------------------------------------

    def _get_version(self, rpc_request):
        """ Get the version of this project.
        """
        try:
            rpc_response = self._get_rpc_response(rpc_request['id'])
            rpc_response['result'] = self._version
            json_dump = json.dumps(rpc_response)
        except Exception as ex:
            return self._return_error(rpc_request['id'], 'Could not determine version. (%s)' % str(ex))
        else:
            return json_dump

    def _poll(self, rpc_request):
        """ Return the log messages to the browser.
        """
        try:
            rpc_response = self._get_rpc_response(rpc_request['id'])
            rpc_response['result'] = self._log.get_message()
            json_dump = json.dumps(rpc_response)
        except Exception:
            # The message could not transfered to the browser. So re queue it!
            self._log.requeue(rpc_response['result'])
        else:
            return json_dump

    def _get_file_list(self, rpc_request):
        """ Return the list of all files/folder to the browser.
        """
        try:
            code_folder = os.path.join(self._CODE_ROOT, rpc_request['params'].strip('/\\'))
            example_folder = os.path.join(self._EXAMPLE_ROOT, rpc_request['params'].strip('/\\'))

            files_usercode = []
            rpc_response = self._get_rpc_response(rpc_request['id'])
            if os.path.exists(code_folder):
                files_usercode = os.listdir(code_folder)
                files_usercode.sort()
            files_examples = os.listdir(example_folder)
            files_examples.sort()
            rpc_response['result'] = files_examples + files_usercode
            rpc_response['result'].sort()
            json_dump = json.dumps(rpc_response)

        except Exception as e:
            return self._return_error(rpc_request['id'], 'Could not get a file list for the folder. (%s)' % str(e))
        else:
            return json_dump

    def _create_folder(self, rpc_request):
        """ Creates the folder on the device.
        """
        try:
            new_folder = os.path.join(self._CODE_ROOT, rpc_request['params'].strip('/\\'))

            if not os.path.exists(new_folder):
                os.makedirs(new_folder)

            rpc_response = self._get_rpc_response(rpc_request['id'])
            json_dump = json.dumps(rpc_response)
        except Exception as ex:
            return self._return_error(rpc_request['id'], 'Could not create the folder. (%s)' % str(ex))
        else:
            return json_dump

    def _load_file(self, rpc_request):
        """ Return the content of the file back to the browser.
        """
        try:
            # TODO: Extract file base path (examples/user code) from rpc call and remove this hack
            filename = os.path.join(self._CODE_ROOT, rpc_request['params'].strip('/\\'))
            if not os.path.exists(filename):
                filename = os.path.join(self._EXAMPLE_ROOT, rpc_request['params'].strip('/\\'))

            rpc_response = self._get_rpc_response(rpc_request['id'])
            f = open(filename, 'r')
            rpc_response['result'] = f.read()
            f.close()
            json_dump = json.dumps(rpc_response)
        except Exception as ex:
            return self._return_error(rpc_request['id'], 'Could not get the content of the file. (%s)' % str(ex))
        else:
            return json_dump

    def _save_file(self, rpc_request):
        """ Save the received content on the local disk.
        """
        # Store all incoming data into the file.
        try:
            rpc_response = self._get_rpc_response(rpc_request['id'])
            filename = os.path.join(self._CODE_ROOT, rpc_request['params']['filename'].strip('/\\'))
            with open(filename, 'w') as file:
                file.writelines(rpc_request['params']['data'])
            rpc_response['result'] = 'File %s saved.' % rpc_request['params']['filename']
            json_dump = json.dumps(rpc_response)
        except Exception as ex:
            return self._return_error(rpc_request['id'], 'Could not save the content of the file. (%s)' % str(ex))
        else:
            return json_dump

    def _get_is_running(self, rpc_request):
        """ Get the current running state of the device
        """
        try:
            rpc_response = self._get_rpc_response(rpc_request['id'])
            rpc_response['result'] = self._is_running
            json_dump = json.dumps(rpc_response)
        except Exception as ex:
            return self._return_error(rpc_request['id'],
                                      'Could not determine if there is a program running. (%s)' % str(ex))
        else:
            return json_dump

    def _execute(self, rpc_request):
        """ Store the data on a local file and execute them.
        """
        if self._is_running is False:
            try:
                self._is_running = True

                filename = os.path.join(tempfile.gettempdir(), 'execute.py')

                with open(filename, 'wt') as file:
                    file.writelines(self._replace_hucon_requests(rpc_request['params']))
                file.close()

                # Wait for a while until the file is really closed before it can be executed.
                time.sleep(0.2)

                self._run_file(filename)

            except Exception as ex:
                self._log.put('Error: %s' % str(ex))

            self._is_running = False
            self._current_proc = None

        else:
            return self._return_error(rpc_request['id'], 'There is a program running.', 503)

        rpc_response = self._get_rpc_response(rpc_request['id'])
        return json.dumps(rpc_response)

    def _run(self, rpc_request):
        """ Run the file which is saved on the device
        """
        if self._is_running is False:
            try:
                filename = os.path.join(self._CODE_ROOT, rpc_request['params'].strip('/\\'))

                self._is_running = True

                self._run_file(filename)

            except Exception as ex:
                self._log.put('Error: %s' % str(ex))

            self._is_running = False
            self._current_proc = None
        else:
            return self._return_error(rpc_request['id'], 'There is a program running.', 503)

        rpc_response = self._get_rpc_response(rpc_request['id'])
        return json.dumps(rpc_response)

    def _kill(self, rpc_request):
        """ Kill the current running process
        """
        if self._current_proc:
            try:
                self._current_proc.send_signal(signal.CTRL_C_EVENT)
            except Exception:
                pass
        if self._current_proc:
            try:
                self._current_proc.send_signal(signal.CTRL_BREAK_EVENT)
            except Exception:
                pass
        if self._current_proc:
            try:
                self._current_proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
        time.sleep(0.1)

        rpc_response = self._get_rpc_response(rpc_request['id'])
        rpc_response['result'] = 'Application stopped.'
        return json.dumps(rpc_response)

    def _get_possible_post_data(self, rpc_request):
        """ Return the json of available post data events.
        """
        try:
            rpc_response = self._get_rpc_response(rpc_request['id'])
            with open(os.path.join(tempfile.gettempdir(), 'possible_events'), 'r') as file:
                rpc_response['result'] = json.load(file)
            file.close()
        except Exception as ex:
            return self._return_error(rpc_request['id'],
                                      'Could not retrieve the list of possible events. (%s)' % str(ex), 500)
        else:
            return json.dumps(rpc_response)

    def _event(self, rpc_request):
        """ Fire the event on the device.
        """
        if self._is_running:

            try:
                if os.name == 'nt':
                    return self._return_error(rpc_request['id'], 'Could not set the event on windows machines.', 500)

                os.kill(self._current_proc.pid, signal.SIGRTMIN + rpc_request['params'])
            except Exception as ex:
                return self._return_error(rpc_request['id'], 'Could not set the event. (%s)' % str(ex), 503)
        else:
            return self._return_error(rpc_request['id'], 'There is no program running.', 503)

        rpc_response = self._get_rpc_response(rpc_request['id'])
        return json.dumps(rpc_response)

    def _check_update(self, rpc_request):
        """ Check if there is an update available.
        """
        try:
            proc = subprocess.Popen(['sh', self._UPDATE_FILE, '-c'], bufsize=0, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

            while True:
                output = proc.stdout.readline()
                if output == '' and proc.poll() is not None:
                    break
                if output:
                    self._log.put(output.strip())
            proc.poll()

            rpc_response = self._get_rpc_response(rpc_request['id'])
            if proc.returncode == 1:
                rpc_response['result'] = True
            else:
                rpc_response['result'] = False
        except Exception as ex:
            return self._return_error(rpc_request['id'], 'Could not get a version. (%s)' % str(ex), 500)
        else:
            return json.dumps(rpc_response)

    def _update(self, rpc_request):
        """ Update all files from the project.
        """
        try:
            # Update the system first.
            self._log.put('The system will be updated and needs a few seconds.\n')
            proc = subprocess.Popen(['sh', self._UPDATE_FILE, '-u'], bufsize=0, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

            while True:
                output = proc.stdout.readline()
                if output == '' and proc.poll() is not None:
                    break
                if output:
                    self._log.put(output.strip())
            proc.poll()

            # Do a restart.
            proc = subprocess.Popen(['sh', self._UPDATE_FILE, '-r'], bufsize=0, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

            while True:
                output = proc.stdout.readline()
                if output == '' and proc.poll() is not None:
                    break
                if output:
                    self._log.put(output.strip())
            proc.poll()

        except Exception as ex:
            return self._return_error(rpc_request['id'], 'Could not perform an update. (%s)' % str(ex), 500)
        else:
            # This should never be reached in term of the system reboot
            return self._return_error(rpc_request['id'], 'Could not perform an update.', 500)

    def _shutdown(self, rpc_request):
        """ Shutdown the robot.
        """
        try:
            self._log.put('The system will be shutdown.\n')
            proc = subprocess.Popen(['sh', self._UPDATE_FILE, '-s'], bufsize=0, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

            while True:
                output = proc.stdout.readline()
                if output == '' and proc.poll() is not None:
                    break
                if output:
                    self._log.put(output.strip())
            proc.poll()
        except Exception as ex:
            return self._return_error(rpc_request['id'], 'Could not shutdown the system. (%s)' % str(ex), 500)
        else:
            # This should never be reached in term of the system shutdown.
            return self._return_error(rpc_request['id'], 'Could not shutdown the system.', 500)
