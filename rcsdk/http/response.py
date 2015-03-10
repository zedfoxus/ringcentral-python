# !/usr/bin/env python
# encoding: utf-8
import json
from email.feedparser import FeedParser

from .headers import *


BOUNDARY_SEPARATOR = '--'
BODY_SEPARATOR = "\n\n"
UNAUTHORIZED_STATUS = 401


class Response(Headers):
    def __init__(self, status, raw, headers=None):
        """
         Builds response by parsing raw response on-the-wire. Should be refactored out. Parsing should not happen here.
         It's not the place for this.
        :param status:
        :param raw:
        :param headers:
        :return:
        """
        Headers.__init__(self)

        self.__body = ''
        self.__raw = raw.replace('\r', '')
        self.__raw_headers = ''
        self.__status = status

        if status is None:
            raise Exception('Empty status was received')

        if isinstance(headers, dict):
            self.set_headers(headers)
            self.__body = raw
            self.__parse_headers()

        elif self.__raw.find(BODY_SEPARATOR) > 0:
            self.__raw_headers, self.__body = self.__raw.split(BODY_SEPARATOR, 1)

        else:
            self.__body = self.__raw

    def check_status(self):
        """
        Returns True if HTTP status is 200 OK
        :return:
        """
        return 200 <= self.__status < 300

    def get_body(self):
        """
        Returns whole response body as a string.
        :return:
        """
        return self.__body

    def get_data(self, as_object=False):
        if self.is_json():
            return self.get_json(as_object)
        elif self.is_multipart():
            return self.get_responses()
        else:
            return self.get_body()

    def get_json(self, as_object=False):
        """
        Returns:
         - JSON for application/json response,
         - or raises exception
        """
        if self.is_json():
            parsed = json.loads(self.__body)
            return parsed if not as_object else unfold(parsed)
        else:
            raise Exception('Response is not JSON')

    def get_raw(self):
        """
        Raw response with headers and body. As seen on the wire. (WTF?!)
        :return:
        """
        return self.__raw

    def get_status(self):
        """
        Returns HTTP status code
        :return:
        """
        return self.__status

    def get_responses(self):
        """
        Returns sub-responses, if this response is multipart
        :return:
        """
        if self.is_multipart():
            parts = self.__break_into_parts()
            if len(parts) < 1:
                # sic! not specific extension
                raise Exception("Malformed Batch Response (not enough parts)")
            # TODO Defensive checking for part[0] content type
            # TODO JSON parsing errors handling
            statuses = json.loads(parts[0].get_payload())
            if len(statuses["response"]) != len(parts) - 1:
                raise Exception("Malformed Batch Response (not-consistent number of parts)")

            responses = []

            for response, payload in zip(statuses["response"], parts[1:]):
                responses.append(Response(response["status"], payload.get_payload(), dict(payload)))

            return responses

        else:
            raise Exception('Response is not Batch (Multipart)')

    def __parse_headers(self):
        """
        Sic! HTTP clients do this!
        :return:
        """
        headers = self.__raw_headers.split('\n')
        for h in filter(lambda x: x.find(HEADER_SEPARATOR) >= 0, headers):
            k, v = h.split(HEADER_SEPARATOR, 1)
            self.set_header(k.strip(), v.strip())

    def __break_into_parts(self):

        p = FeedParser()
        for h in self.get_headers_array():
            p.feed(h + "\r\n")
        p.feed("\r\n")
        p.feed(self.__body)
        msg = p.close()
        parts = msg.get_payload()
        return parts


PYTHON_KEYWORDS = (
    "and", "del", "from", "not", "while", "as", "elif", "global", "or", "with", "assert", "else", "if", "pass", "yield",
    "break", "except", "import", "rint", "class", "exec", "in", "raise", "continue", "finally", "is", "return", "def",
    "for", "lambda", "try",)


class JsonObject:
    def __init__(self):
        pass


def safe_name(n):
    if n in PYTHON_KEYWORDS:
        return n + "_"
    else:
        return n


def unfold(d):
    if isinstance(d, dict):
        o = JsonObject()
        for k, v in d.iteritems():
            o.__dict__[safe_name(k)] = unfold(v)
        return o
    elif isinstance(d, list):
        o = [unfold(x) for x in d]
        return o
    else:
        return d