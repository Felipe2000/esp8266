#
# Copyright (c) dushin.net  All Rights Reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of dushin.net nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY dushin.net ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL dushin.net BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import ujson
import uhttpd


class Handler:
    def __init__(self, handlers):
        self._handlers = handlers

    #
    # callbacks
    #

    def handle_request(self, http_request):
        relative_path = uhttpd.get_relative_path(http_request)
        path_part, query_params = self.extract_query(relative_path)
        components = path_part.strip('/').split('/')
        prefix, handler, context = self.find_handler(components)
        if handler:
            headers = http_request['headers']
            json_body = None
            if all(['body' in http_request,
                    headers.get('content-type') == "application/json"]):
                try:
                    json_body = ujson.loads(http_request['body'])
                except Exception as e:
                    raise uhttpd.BadRequestException("Failed to load JSON: {}".format(e))
            verb = http_request['verb'].lower()
            api_request = {
                'prefix': prefix,
                'context': context,
                'query_params': query_params,
                'body': json_body,
                'http': http_request
            }
            try:
                response = getattr(handler, verb)(api_request)
                # if verb == 'get':
                #     response = handler.get
                # elif verb == 'put':
                #     response = handler.put(api_request)
                # elif verb == 'post':
                #     response = handler.post(api_request)
                # elif verb == 'delete':
                #     response = handler.delete(api_request)
            except AttributeError:
                # TODO add support for more verbs!
                error_message = "Unsupported verb: {}".format(verb)
                raise uhttpd.BadRequestException(error_message)
        else:
            error_message = "No handler found for components {}".format(components)
            raise uhttpd.NotFoundException(error_message)
        response_headers = {}
        if response is not None:
            if type(response) is dict:
                data = ujson.dumps(response).encode('UTF-8')
                response_headers['content-type'] = "application/json"
            elif type(response) is bytes:
                data = response
                response_headers['content-type'] = "application/binary"
            else:
                raise Exception("Response from API Handler is neither dict nor bytearray nor None")
            body = lambda stream: stream.awrite(data)
        else:
            body = None
        response_headers['content-length'] = len(data)
        ret = {'code': 200,
               'headers': response_headers,
               'body': body}
        return ret

    #
    # Internal operations
    #

    def find_handler(self, components):
        for prefix, handler in self._handlers:
            prefix_len = len(prefix)
            if prefix == components[:prefix_len]:
                return prefix, handler, components[prefix_len:]
        return None, None, None

    @staticmethod
    def extract_query(path):
        try:
            path_, query = path.split("?")
            if not query:
                return path, None
        except ValueError:
            raise uhttpd.BadRequestException("Malformed path: {}".format(path))
        query_params = {}
        components = [component for component in query.split("&")
                      if component.strip()]
        for qparam_component in components:
            try:
                parameter, value = qparam_component.split("=")
                if not parameter:
                    raise ValueError
            except ValueError:
                message = "Invalid query parameter: {}".format(qparam_component)
                raise uhttpd.BadRequestException(message)
            query_params[parameter] = value
        return path_, query_params
