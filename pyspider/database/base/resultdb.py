#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Binux<i@binux.me>
#         http://binux.me
# Created on 2014-10-11 18:40:03

# result schema
{
'result': {
    'taskid': str, # new, not changeable
    'project': str, # new, not changeable
    'url': str, # new, not changeable
    'result': str, # json string
    'updatetime': int,
    }
}

class ResultDB(object):
    """
    database for result
    """

    def save(self, project, taskid, url, result):
        raise NotImplementedError

    def select(self, project, fields=None, offset=0, limit=None):
        raise NotImplementedError

    def count(self, project):
        raise NotImplementedError

    def get(self, project, taskid, fields=None):
        raise NotImplementedError

    def drop(self, project):
        raise NotImplementedError
